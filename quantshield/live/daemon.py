import argparse
import os
import signal
import subprocess
import sys
import time
from collections.abc import Callable
from datetime import UTC, date, datetime

import numpy as np
import pandas as pd

from quantshield.broker.zerodha import token_fresh
from quantshield.calendar import IST, is_india_holiday, is_india_market_hours
from quantshield.config import EMERGENCY_TRIGGERS, INDIA_TICKERS
from quantshield.live.notify import format_emergency, notify
from quantshield.paths import INTRADAY, MONITOR, PORTFOLIO, ROOT
from quantshield.utils import atomic_write_json, load_json
from quantshield.utils import log as _log

TAG = 'monitor'
SCRIPT_DIR = str(ROOT)
HEARTBEAT_PATH = str(MONITOR / 'heartbeat.json')
EMERGENCY_PATH = str(MONITOR / 'EMERGENCY.json')
EMERGENCY_LOG_PATH = str(MONITOR / 'emergency_log.json')
LOGIN_NOTIFY_PATH = str(MONITOR / '.zerodha_login_notified')
SNAPSHOT_MARKER_PATH = str(MONITOR / '.snapshot_attempts')
DEPLOY_SCRIPT = str(ROOT / 'scripts' / 'deploy_dashboard.sh')
SMALL_TRACK_PATH = str(PORTFOLIO / 'small_track_record.json')
SMALL_PLAN_PATH = str(PORTFOLIO / 'small_account_plan.json')
SMALL_EXEC_JOURNAL_PATH = str(PORTFOLIO / 'execution_journal.json')
FEED_HEARTBEAT_PATH = str(INTRADAY / 'feed_heartbeat.json')
FEED_STALE_NOTIFY_PATH = str(INTRADAY / '.feed_stale_notified')
FEED_DEAD_S = 24 * 3600
KILL_PATH = str(ROOT / 'data' / 'KILL')
KILL_NOTIFY_PATH = str(MONITOR / '.kill_notified')
DEPLOY_NOTIFY_PATH = str(MONITOR / '.deploy_failed_notified')
SMALL_ENGINE_MODULE = 'quantshield.live.planner'
SMALL_EXECUTE_MODULE = 'quantshield.live.executor'
SMALL_SNAPSHOT_HOUR = 15
SMALL_SNAPSHOT_MINUTE = 35
SMALL_SNAPSHOT_TIMEOUT = 300
SMALL_SNAPSHOT_MAX_ATTEMPTS = 2
SMALL_TRADE_START = (9, 25)
SMALL_TRADE_END = (14, 30)
SMALL_PLAN_TIMEOUT = 300
SMALL_EXECUTE_TIMEOUT = 1500
DEPLOY_TIMEOUT = 600
FEED_STALE_S = 180
RETRY_ATTEMPTS = 3
RETRY_BACKOFF = 10
STALE_BDAYS = 2
MONITOR_TICKERS = ['^INDIAVIX', '^VIX'] + list(INDIA_TICKERS)
EXECUTE_EXIT_MEANINGS = {
    2: 'KILL file present',
    3: 'broker auth/read failure',
    4: 'holdings reconcile mismatch',
    5: 'another executor instance running',
    6: 'post-trade state refresh failed',
}
SELF_NOTIFIED_EXITS = (2, 3, 4, 6)

_shutdown = False


def log(msg: str) -> None:
    _log(msg, TAG)


def _handle_signal(signum: int, frame: object) -> None:
    global _shutdown
    _shutdown = True
    log(f"received signal {signum}, shutting down")


def _retry_yfinance[T](func: Callable[[], T]) -> T:
    last_err: Exception = RuntimeError('no attempts')
    for attempt in range(RETRY_ATTEMPTS):
        try:
            return func()
        except Exception as e:
            last_err = e
            if attempt < RETRY_ATTEMPTS - 1:
                log(f"yfinance retry {attempt + 1}/{RETRY_ATTEMPTS}: {e}")
                time.sleep(RETRY_BACKOFF)
    raise last_err


def stale_tickers(close: pd.DataFrame, today: date, max_bdays: int = STALE_BDAYS) -> list[str]:
    if close.empty:
        return list(close.columns)
    present = close.notna()
    cols = present.columns[present.any()]
    missing = [c for c in close.columns if c not in cols]
    if len(cols) == 0:
        return missing
    last = pd.DatetimeIndex(present[cols][::-1].idxmax().values)
    if last.tz is not None:
        last = last.tz_convert(None)
    age = np.busday_count(last.values.astype('datetime64[D]'), np.datetime64(today))
    return [c for c, a in zip(cols, age, strict=True) if a > max_bdays] + missing


def _write_heartbeat_error(error_type: str, error_msg: str) -> None:
    try:
        atomic_write_json(HEARTBEAT_PATH, {
            'timestamp': datetime.now(UTC).isoformat(),
            'status': error_type,
            'error': str(error_msg),
            'us_vix': None,
            'india_vix': None,
        })
    except Exception:
        pass


def _today() -> str:
    return datetime.now(IST).strftime('%Y-%m-%d')


def _snapshot_attempts(today: str) -> int:
    try:
        with open(SNAPSHOT_MARKER_PATH) as f:
            marked, count = f.read().split()
        return int(count) if marked == today else 0
    except (OSError, ValueError):
        return 0


def _bump_snapshot_attempts(today: str) -> None:
    count = _snapshot_attempts(today) + 1
    os.makedirs(os.path.dirname(SNAPSHOT_MARKER_PATH), exist_ok=True)
    with open(SNAPSHOT_MARKER_PATH, 'w') as f:
        f.write(f"{today} {count}")


def small_snapshot_due() -> bool:
    now = datetime.now(IST)
    if now.weekday() >= 5 or is_india_holiday(now.date()):
        return False
    if (now.hour, now.minute) < (SMALL_SNAPSHOT_HOUR, SMALL_SNAPSHOT_MINUTE):
        return False
    today = now.strftime('%Y-%m-%d')
    if _snapshot_attempts(today) >= SMALL_SNAPSHOT_MAX_ATTEMPTS:
        return False
    track = load_json(SMALL_TRACK_PATH)
    if not isinstance(track, dict):
        return True
    return not any(s.get('date') == today for s in track.get('snapshots', []))


def _venv_python() -> str:
    venv_python = str(ROOT / 'venv' / 'bin' / 'python')
    return venv_python if os.path.exists(venv_python) else sys.executable


def _marker_is_today(path: str, today: str) -> bool:
    try:
        with open(path) as f:
            return f.read().strip() == today
    except OSError:
        return False


def _write_marker(path: str, today: str) -> None:
    try:
        with open(path, 'w') as f:
            f.write(today)
    except OSError:
        pass


def _notify_safe(msg: str, level: str = 'warning') -> None:
    try:
        notify(msg, level=level)
    except Exception as e:
        log(f"notify failed: {e}")


def _notify_login_needed_once(today: str) -> None:
    if _marker_is_today(LOGIN_NOTIFY_PATH, today):
        return
    _notify_safe("Zerodha access token expired; run the daily login before 09:25 IST")
    _write_marker(LOGIN_NOTIFY_PATH, today)


def small_trading_window() -> bool:
    now = datetime.now(IST)
    if now.weekday() >= 5 or is_india_holiday(now.date()):
        return False
    return SMALL_TRADE_START <= (now.hour, now.minute) <= SMALL_TRADE_END


def _plan_is_today(plan: object, today: str) -> bool:
    return isinstance(plan, dict) and str(plan.get('generated', ''))[:10] == today


def run_small_trading() -> None:
    if not small_trading_window():
        return
    today = _today()
    journal = load_json(SMALL_EXEC_JOURNAL_PATH) or []
    if any(e.get('date') == today for e in journal):
        return
    plan = load_json(SMALL_PLAN_PATH)
    if not _plan_is_today(plan, today):
        if not token_fresh():
            _notify_login_needed_once(today)
            return
        log("generating small account plan")
        try:
            subprocess.run([_venv_python(), '-m', SMALL_ENGINE_MODULE], cwd=SCRIPT_DIR, timeout=SMALL_PLAN_TIMEOUT)
        except Exception as e:
            log(f"small plan generation failed: {e}")
            return
        plan = load_json(SMALL_PLAN_PATH)
        if not _plan_is_today(plan, today):
            log("plan generation did not produce today's plan; skipping execution")
            return
    if not plan.get('orders'):
        return
    if os.path.exists(KILL_PATH):
        if not _marker_is_today(KILL_NOTIFY_PATH, today):
            _notify_safe("Execution halted: data/KILL present. Remove it to resume auto-trading.")
            _write_marker(KILL_NOTIFY_PATH, today)
        return
    if not token_fresh():
        _notify_login_needed_once(today)
        return
    log("running executor for today's plan")
    try:
        result = subprocess.run([_venv_python(), '-m', SMALL_EXECUTE_MODULE], cwd=SCRIPT_DIR, timeout=SMALL_EXECUTE_TIMEOUT)
    except subprocess.TimeoutExpired:
        log(f"executor timed out after {SMALL_EXECUTE_TIMEOUT}s")
        _notify_safe(f"executor timed out after {SMALL_EXECUTE_TIMEOUT}s and was killed; check Kite for live orders immediately")
        return
    except Exception as e:
        log(f"executor failed: {e}")
        _notify_safe(f"executor failed to run: {e}")
        return
    if result.returncode != 0:
        why = EXECUTE_EXIT_MEANINGS.get(result.returncode, 'abnormal exit')
        log(f"executor exited {result.returncode} ({why})")
        if result.returncode not in SELF_NOTIFIED_EXITS:
            _notify_safe(f"executor exited {result.returncode} ({why}); check daemon.log and Kite")


def run_small_snapshot() -> None:
    today = _today()
    _bump_snapshot_attempts(today)
    if not token_fresh():
        _notify_login_needed_once(today)
        log("snapshot skipped: Zerodha access token is not fresh")
        return
    try:
        result = subprocess.run(
            [_venv_python(), '-m', SMALL_ENGINE_MODULE, '--snapshot'],
            cwd=SCRIPT_DIR,
            timeout=SMALL_SNAPSHOT_TIMEOUT,
        )
        if result.returncode != 0:
            log(f"WARNING: small account snapshot exited {result.returncode}")
    except Exception as e:
        log(f"WARNING: small account snapshot failed: {e}")


def check_feed_freshness() -> None:
    hb = load_json(FEED_HEARTBEAT_PATH)
    if not hb or not hb.get('ts'):
        return
    try:
        ts = datetime.fromisoformat(hb['ts'])
        age = (datetime.now(UTC) - ts).total_seconds()
    except (TypeError, ValueError):
        return
    if age <= FEED_STALE_S or age > FEED_DEAD_S:
        return
    today = _today()
    if _marker_is_today(FEED_STALE_NOTIFY_PATH, today):
        return
    _notify_safe(f"intraday feed heartbeat stale ({int(age)}s) during market hours; paper engine has no bars")
    _write_marker(FEED_STALE_NOTIFY_PATH, today)


def load_tail(path: str) -> str:
    try:
        with open(path) as f:
            lines = [line.rstrip() for line in f if line.strip()]
    except OSError:
        return ''
    return lines[-1] if lines else ''


def deploy_dashboard() -> None:
    try:
        log("exporting and deploying dashboard")
        result = subprocess.run([DEPLOY_SCRIPT], cwd=SCRIPT_DIR, timeout=DEPLOY_TIMEOUT,
                                capture_output=True, text=True)
        log(f"deploy_dashboard.sh exited {result.returncode}")
        if result.returncode != 0:
            tail = load_tail(str(MONITOR / 'deploy.log')) or result.stderr.strip()
            if tail:
                log(tail)
            today = _today()
            if not _marker_is_today(DEPLOY_NOTIFY_PATH, today):
                _notify_safe(f"dashboard deploy failed (exit {result.returncode}): {tail[-200:]}")
                _write_marker(DEPLOY_NOTIFY_PATH, today)
    except Exception as e:
        log(f"dashboard deploy failed: {e}")


def _download_close() -> pd.DataFrame:
    import yfinance as yf
    data = yf.download(MONITOR_TICKERS, period='5d', auto_adjust=False, progress=False, threads=False)
    if data is None or data.empty:
        return pd.DataFrame()
    return data['Close'] if isinstance(data.columns, pd.MultiIndex) else data


def fetch_market_data() -> dict:
    close = _retry_yfinance(_download_close)
    data: dict = {'us_vix': None, 'india_vix': None, 'daily_changes': {}}
    if close.empty:
        return data
    last = close.ffill().iloc[-1]
    for key, ticker in (('us_vix', '^VIX'), ('india_vix', '^INDIAVIX')):
        if ticker in close.columns and pd.notna(last[ticker]):
            data[key] = round(float(last[ticker]), 2)
    sats = [t for t in INDIA_TICKERS if t in close.columns]
    rows = close[sats].dropna(how='all')
    if len(rows) >= 2:
        pct = (rows.iloc[-1] / rows.iloc[-2] - 1) * 100
        data['daily_changes'] = {t: round(float(v), 2) for t, v in pct.dropna().items()}
    for t in stale_tickers(close, datetime.now(IST).date()):
        log(f"STALE_DATA: {t} has no print in the last {STALE_BDAYS} business days")
    return data


def check_triggers(market_data: dict) -> tuple[list[str], list[str]]:
    triggers: list[str] = []
    affected: list[str] = []
    us_vix = market_data.get('us_vix')
    india_vix = market_data.get('india_vix')
    if us_vix is not None and us_vix > EMERGENCY_TRIGGERS['us_vix']:
        triggers.append(f"US VIX at {us_vix} > {EMERGENCY_TRIGGERS['us_vix']}")
    if india_vix is not None and india_vix > EMERGENCY_TRIGGERS['india_vix']:
        triggers.append(f"India VIX at {india_vix} > {EMERGENCY_TRIGGERS['india_vix']}")
    drop = EMERGENCY_TRIGGERS['daily_drop_pct']
    for ticker, pct in market_data.get('daily_changes', {}).items():
        if pct <= -drop:
            triggers.append(f"{ticker} down {pct}% today")
            affected.append(ticker)
    return triggers, affected


def write_heartbeat(market_data: dict) -> dict:
    heartbeat = {
        'timestamp': datetime.now(UTC).isoformat(),
        'status': 'all_clear',
        'us_vix': market_data.get('us_vix'),
        'india_vix': market_data.get('india_vix'),
    }
    atomic_write_json(HEARTBEAT_PATH, heartbeat)
    return heartbeat


def write_emergency(triggers: list[str], affected: list[str], market_data: dict) -> dict:
    emergency = {
        'active': True,
        'triggers': triggers,
        'last_check': datetime.now(UTC).isoformat(),
        'us_vix': market_data.get('us_vix'),
        'india_vix': market_data.get('india_vix'),
        'affected_tickers': affected,
    }
    atomic_write_json(EMERGENCY_PATH, emergency)
    elog = load_json(EMERGENCY_LOG_PATH)
    if not isinstance(elog, list):
        elog = []
    elog.append(emergency)
    atomic_write_json(EMERGENCY_LOG_PATH, elog)
    return emergency


def _no_data(market_data: dict) -> bool:
    return market_data['us_vix'] is None and market_data['india_vix'] is None and not market_data['daily_changes']


def run_check(auto_execute: bool = False) -> None:
    try:
        now = datetime.now(IST)
        if auto_execute:
            run_small_trading()
        snapshot_ran = False
        if small_snapshot_due():
            log("running small account daily snapshot")
            run_small_snapshot()
            snapshot_ran = True
        if not is_india_market_hours(now):
            if snapshot_ran:
                deploy_dashboard()
            log(f"{now.isoformat()} outside market hours or holiday, skipping")
            return
        log(f"{now.isoformat()} running check")
        try:
            market_data = fetch_market_data()
        except Exception as e:
            log(f"NETWORK_ERROR: all retries failed: {e}")
            _write_heartbeat_error('NETWORK_ERROR', str(e))
            return
        if _no_data(market_data):
            log("NO_DATA: yfinance returned no usable rows")
            _write_heartbeat_error('NO_DATA', 'yfinance returned no usable rows')
        else:
            triggers, affected = check_triggers(market_data)
            if triggers:
                log(f"EMERGENCY: {triggers}")
                emergency = write_emergency(triggers, affected, market_data)
                notify(format_emergency(emergency), level='emergency')
            else:
                write_heartbeat(market_data)
                log(f"all clear: VIX={market_data['us_vix']}, India VIX={market_data['india_vix']}")
        check_feed_freshness()
        deploy_dashboard()
    except Exception as e:
        log(f"CRITICAL ERROR in run_check: {e}")
        _write_heartbeat_error('CRITICAL_ERROR', str(e))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--interval', type=int, default=30)
    parser.add_argument('--auto-execute', action='store_true')
    parser.add_argument('--once', action='store_true')
    args = parser.parse_args()
    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)
    log(f"starting daemon, interval={args.interval}min, auto_execute={args.auto_execute}")
    if args.once:
        run_check(auto_execute=args.auto_execute)
        return
    while not _shutdown:
        try:
            run_check(auto_execute=args.auto_execute)
        except Exception as e:
            log(f"unhandled error: {e}")
            _write_heartbeat_error('UNHANDLED_ERROR', str(e))
        for _ in range(args.interval * 60):
            if _shutdown:
                break
            time.sleep(1)
    log("shutdown complete")


if __name__ == '__main__':
    main()
