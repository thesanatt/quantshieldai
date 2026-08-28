import os
import sys
import time
from datetime import UTC, datetime
from typing import Any

from quantshield.calendar import is_india_holiday
from quantshield.intraday.candles import (
    NIFTY_INDEX_TOKEN,
    SESSION_CLOSE,
    SESSION_OPEN,
    SYMBOLS,
    day_path,
    instrument_token,
)
from quantshield.paths import INTRADAY
from quantshield.utils import IST, append_jsonl, atomic_write_json, log, now_ist

INTRADAY_DIR = str(INTRADAY)
TICKS_DIR = str(INTRADAY / 'ticks')
HEARTBEAT_PATH = str(INTRADAY / 'feed_heartbeat.json')

HARD_EXIT = (15, 35)
WAIT_UNTIL = (9, 5)
STALE_AUTH_EXIT = 4
AUTH_NEEDED_EXIT = 3
AUTH_FAIL_LIMIT = 3
HEARTBEAT_S = 5
WAIT_POLL_S = 30


def _log(msg: str) -> None:
    log(f"{now_ist().isoformat(timespec='seconds')} {msg}", 'feed')


class BarAggregator:
    def __init__(self) -> None:
        self.current: dict[int, dict] = {}
        self.last_cum_vol: dict[int, int] = {}

    def on_tick(self, token: int, price: float, cum_vol: int | None, ts: datetime) -> list[dict]:
        minute = ts.replace(second=0, microsecond=0)
        cv = int(cum_vol or 0)
        bar = self.current.get(token)
        done: list[dict] = []
        if bar is not None and bar['minute'] != minute:
            done.append(self.finalize(token))
            bar = None
        if bar is None:
            self.current[token] = {
                'minute': minute, 'open': price, 'high': price, 'low': price,
                'close': price, 'cum_vol': cv, 'cum0': cv, 'ticks': 1,
            }
        else:
            bar['high'] = max(bar['high'], price)
            bar['low'] = min(bar['low'], price)
            bar['close'] = price
            bar['cum_vol'] = max(bar['cum_vol'], cv)
            bar['ticks'] += 1
        return done

    def finalize(self, token: int) -> dict:
        bar = self.current.pop(token)
        prev = self.last_cum_vol.get(token, bar['cum0'])
        vol = max(0, bar['cum_vol'] - prev)
        self.last_cum_vol[token] = bar['cum_vol']
        return {
            'ts': bar['minute'].isoformat(),
            'open': bar['open'], 'high': bar['high'], 'low': bar['low'], 'close': bar['close'],
            'volume': vol, 'ticks': bar['ticks'],
        }

    def flush(self) -> dict[int, dict]:
        return {token: self.finalize(token) for token in list(self.current)}


def append_bar(symbol: str, bar: dict, day: str) -> None:
    append_jsonl(day_path(symbol, day, TICKS_DIR), bar)


def session_bounds(now: datetime) -> tuple[datetime, datetime] | None:
    if now.weekday() >= 5 or is_india_holiday(now.date()):
        return None
    open_dt = now.replace(hour=SESSION_OPEN[0], minute=SESSION_OPEN[1], second=0, microsecond=0)
    close_dt = now.replace(hour=SESSION_CLOSE[0], minute=SESSION_CLOSE[1], second=0, microsecond=0)
    return open_dt, close_dt


def wait_for_session() -> bool:
    while True:
        now = now_ist()
        if session_bounds(now) is None:
            _log('no session today (weekend/holiday)')
            return False
        if (now.hour, now.minute) >= HARD_EXIT:
            _log('session already over')
            return False
        if (now.hour, now.minute) >= WAIT_UNTIL:
            return True
        time.sleep(WAIT_POLL_S)


def write_heartbeat(state: dict) -> None:
    atomic_write_json(HEARTBEAT_PATH, {
        'ts': datetime.now(UTC).isoformat(),
        'connected': state['connected'],
        'bars_written': state['bars'],
        'last_tick_ts': state['last_tick'],
        'auth_failures': state['auth_fail'],
    }, indent=None)


def notify_safe(msg: str, level: str = 'warning') -> None:
    try:
        from quantshield.live.notify import notify
        notify(msg, level=level)
    except Exception as exc:
        _log(f'notify failed: {exc}')


def resolve_tokens(kite: Any) -> dict[int, str]:
    tokens: dict[int, str] = {NIFTY_INDEX_TOKEN: 'NIFTY50'}
    missing: list[str] = []
    for sym in SYMBOLS:
        tok = instrument_token(kite, sym)
        if tok is None:
            missing.append(sym)
        else:
            tokens[tok] = sym
    if missing:
        raise RuntimeError(f'instrument tokens not found: {missing}')
    return tokens


def run_feed() -> int:
    from kiteconnect import KiteTicker

    from quantshield.broker.zerodha import _get_api_credentials, _load_access_token, get_kite

    api_key, _ = _get_api_credentials()
    access_token = _load_access_token()
    if not access_token:
        _log('no fresh access token; Kite login needed')
        return AUTH_NEEDED_EXIT

    try:
        tokens = resolve_tokens(get_kite())
    except Exception as exc:
        _log(f'instrument resolution failed: {exc}')
        notify_safe(f'intraday feed could not resolve instruments: {exc}')
        return STALE_AUTH_EXIT

    agg = BarAggregator()
    state: dict[str, Any] = {'connected': False, 'bars': 0, 'last_tick': None, 'auth_fail': 0}
    day = now_ist().strftime('%Y-%m-%d')
    kws = KiteTicker(api_key, access_token)

    def on_ticks(ws: Any, ticks: list[dict]) -> None:
        for t in ticks:
            price = t.get('last_price')
            if price is None:
                continue
            stamp = t.get('exchange_timestamp') or t.get('last_trade_time')
            ts = stamp.astimezone(IST).replace(tzinfo=None) if stamp else now_ist()
            token = int(t['instrument_token'])
            for bar in agg.on_tick(token, float(price), t.get('volume_traded'), ts):
                append_bar(tokens[token], bar, day)
                state['bars'] += 1
            state['last_tick'] = ts.isoformat()

    def on_connect(ws: Any, response: Any) -> None:
        ids = list(tokens)
        ws.subscribe(ids)
        ws.set_mode(ws.MODE_FULL, ids)
        state['connected'] = True
        _log(f'connected, subscribed {len(ids)} instruments')

    def on_close(ws: Any, code: int, reason: str) -> None:
        state['connected'] = False
        _log(f'ws closed: {code} {reason}')

    def on_error(ws: Any, code: int, reason: str) -> None:
        _log(f'ws error: {code} {reason}')
        if code in (400, 401, 403):
            state['auth_fail'] += 1

    kws.on_ticks = on_ticks
    kws.on_connect = on_connect
    kws.on_close = on_close
    kws.on_error = on_error
    kws.connect(threaded=True)

    notified_auth = False
    while True:
        now = now_ist()
        if (now.hour, now.minute) >= HARD_EXIT:
            break
        write_heartbeat(state)
        if state['auth_fail'] >= AUTH_FAIL_LIMIT and state['bars'] == 0 and not notified_auth:
            notified_auth = True
            notify_safe(f'intraday feed auth rejected {AUTH_FAIL_LIMIT}x; check the Kite Connect data subscription')
            _log('auth rejected repeatedly with zero bars; exiting')
            try:
                kws.close()
            except Exception:
                pass
            return STALE_AUTH_EXIT
        time.sleep(HEARTBEAT_S)

    for token, bar in agg.flush().items():
        append_bar(tokens.get(token, str(token)), bar, day)
        state['bars'] += 1
    try:
        kws.close()
    except Exception:
        pass
    write_heartbeat(state)
    _log(f'session done, {state["bars"]} bars written')
    return 0


def main() -> None:
    os.makedirs(INTRADAY_DIR, exist_ok=True)
    if not wait_for_session():
        sys.exit(0)
    sys.exit(run_feed())


if __name__ == '__main__':
    main()
