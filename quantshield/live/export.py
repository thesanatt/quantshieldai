import json
import os
from datetime import date, datetime

from dotenv import load_dotenv

from quantshield.broker.zerodha import get_kite
from quantshield.live.executor import LIMIT_BAND, MAX_DAY_TURNOVER, MAX_ORDER_VALUE, MAX_ORDERS_PER_DAY, MAX_PLAN_AGE_H
from quantshield.paths import DASHBOARD, DATA, JOURNAL, MONITOR, PORTFOLIO
from quantshield.utils import IST, atomic_write_json, load_json, read_jsonl
from quantshield.utils import log as _log

TAG = 'export'
CORE = 'NIFTYBEES.NS'
HEARTBEAT_ACTIVE_MIN = 60
OUT_PATH = str(DASHBOARD / 'public' / 'live' / 'dashboard.json')
STATE_PATH = str(PORTFOLIO / 'small_account_state.json')
PLAN_PATH = str(PORTFOLIO / 'small_account_plan.json')
TRACK_PATH = str(PORTFOLIO / 'small_track_record.json')
JOURNAL_PATH = str(PORTFOLIO / 'execution_journal.json')
TRADE_LOG_PATH = str(JOURNAL / 'trade_log.jsonl')
KILL_PATH = str(DATA / 'KILL')
HEARTBEAT_PATH = str(MONITOR / 'heartbeat.json')
GUARDRAILS = {
    'max_order_value': MAX_ORDER_VALUE,
    'max_day_turnover': MAX_DAY_TURNOVER,
    'max_orders_per_day': MAX_ORDERS_PER_DAY,
    'limit_band_pct': round(LIMIT_BAND * 100, 2),
    'max_plan_age_h': MAX_PLAN_AGE_H,
    'order_type': 'LIMIT',
    'product': 'CNC',
}


def log(msg: str) -> None:
    _log(msg, TAG)


def fetch_quotes(symbols: list[str]) -> dict[str, float] | None:
    kite = get_kite()
    if kite is None:
        log("quotes unavailable: no fresh access token")
        return None
    try:
        quotes: dict[str, float] = {}
        for h in kite.holdings():
            sym = f"{h.get('tradingsymbol')}.NS"
            ltp = float(h.get('last_price') or 0.0)
            if sym in symbols and ltp > 0:
                quotes[sym] = ltp
        return quotes
    except Exception as exc:
        log(f"quotes unavailable: {exc}")
        return None


def build_positions(state: dict, quotes: dict[str, float] | None) -> tuple[list[dict], float | None]:
    holdings = {s: int(q) for s, q in (state.get('holdings') or {}).items() if int(q) > 0}
    avg_cost = {s: float(v) for s, v in (state.get('avg_cost') or {}).items()}
    prices = {s: (quotes or {}).get(s) or avg_cost.get(s, 0.0) for s in holdings}
    values = {s: q * prices[s] for s, q in holdings.items()}
    total = float(state.get('cash') or 0.0) + sum(values.values())
    positions = [{'symbol': s.replace('.NS', ''), 'weight_pct': round(v / total * 100, 1) if total > 0 else 0.0}
                 for s, v in sorted(values.items(), key=lambda kv: -kv[1])]
    return positions, (total if quotes is not None else None)


def indexed_curve(track: dict, value_now: float | None, bench_now: float | None, today: str) -> list[dict]:
    snaps = sorted(track.get('snapshots') or [], key=lambda s: s.get('date', ''))
    if not snaps:
        return []
    points = [(s['date'], float(s['portfolio_value']), float(s.get('niftybees_benchmark_value') or s['portfolio_value']))
              for s in snaps]
    if value_now is not None and value_now > 0:
        bench = bench_now if bench_now else points[-1][2]
        if points[-1][0] == today:
            points[-1] = (today, value_now, bench)
        else:
            points.append((today, value_now, bench))
    base_p, base_b = points[0][1], points[0][2]
    return [{'date': d, 'portfolio': round(p / base_p * 100, 3) if base_p > 0 else 100.0,
             'benchmark': round(b / base_b * 100, 3) if base_b > 0 else 100.0} for d, p, b in points]


def drawdown_series(curve: list[dict]) -> list[dict]:
    out = []
    peak = 0.0
    for pt in curve:
        peak = max(peak, pt['portfolio'])
        out.append({'date': pt['date'], 'dd_pct': round((pt['portfolio'] / peak - 1) * 100, 3) if peak > 0 else 0.0})
    return out


def build_metrics(curve: list[dict], track: dict, value_now: float | None, today: str) -> dict:
    if not curve:
        return {'total_return_pct': 0.0, 'bench_return_pct': 0.0, 'alpha_pct': 0.0,
                'max_drawdown_pct': 0.0, 'day_change_pct': None}
    port_ret = curve[-1]['portfolio'] - 100.0
    bench_ret = curve[-1]['benchmark'] - 100.0
    max_dd = min(pt['dd_pct'] for pt in drawdown_series(curve))
    day_change = None
    prior = [s for s in track.get('snapshots') or [] if s.get('date') != today]
    if value_now is not None and prior:
        prev = float(sorted(prior, key=lambda s: s['date'])[-1]['portfolio_value'])
        day_change = round((value_now / prev - 1) * 100, 2) if prev > 0 else None
    return {
        'total_return_pct': round(port_ret, 2),
        'bench_return_pct': round(bench_ret, 2),
        'alpha_pct': round(port_ret - bench_ret, 2),
        'max_drawdown_pct': round(max_dd, 2),
        'day_change_pct': day_change,
    }


def build_execution(journal: list[dict], fills: list[dict], today: str) -> dict:
    slip = [f['slippage_bps'] for f in fills if isinstance(f.get('slippage_bps'), (int, float))]
    return {
        'total_fills': len(fills),
        'avg_slippage_bps': round(sum(slip) / len(slip), 1) if slip else None,
        'orders_today': sum(1 for e in journal if e.get('date') == today and e.get('order_id')),
        'guardrails': GUARDRAILS,
    }


def build_monitor(now: datetime, plan: dict) -> dict:
    heartbeat = load_json(HEARTBEAT_PATH) or {}
    hb_age_min = None
    try:
        ts = datetime.fromisoformat(str(heartbeat.get('timestamp')))
        hb_age_min = max(0, round((now - ts).total_seconds() / 60))
    except (TypeError, ValueError):
        pass
    plan_date = str(plan.get('generated') or '')[:10] or None
    if os.path.exists(KILL_PATH):
        status = 'halted'
    elif plan_date == now.strftime('%Y-%m-%d') or (hb_age_min is not None and hb_age_min <= HEARTBEAT_ACTIVE_MIN):
        status = 'active'
    else:
        status = 'idle'
    return {'heartbeat_age_min': hb_age_min, 'loop_status': status, 'last_plan_date': plan_date}


def build_payload(now: datetime, state: dict, plan: dict, track: dict, journal: list[dict],
                  fills: list[dict], quotes: dict[str, float] | None) -> dict:
    today = now.strftime('%Y-%m-%d')
    positions, value_now = build_positions(state, quotes)
    inception = track.get('inception') or {}
    units = float(inception.get('units') or 0.0)
    core_ltp = (quotes or {}).get(CORE)
    bench_now = units * core_ltp if quotes is not None and core_ltp and units > 0 else None
    curve = indexed_curve(track, value_now, bench_now, today)
    inception_date = inception.get('date')
    days_live = (now.date() - date.fromisoformat(inception_date)).days + 1 if inception_date else 0
    return {
        'generated': now.isoformat(),
        'quotes_live': quotes is not None,
        'account': {
            'broker': 'Zerodha',
            'product': 'CNC delivery',
            'inception_date': inception_date,
            'days_live': max(days_live, 0),
            'positions': positions,
        },
        'metrics': build_metrics(curve, track, value_now, today),
        'series': {'equity_curve': curve, 'drawdown': drawdown_series(curve)},
        'execution': build_execution(journal, fills, today),
        'plan': {
            'generated': plan.get('generated'),
            'regime': plan.get('regime'),
            'orders': len(plan.get('orders') or []),
            'warnings': len(plan.get('warnings') or []),
        },
        'monitor': build_monitor(now, plan),
    }


def main() -> None:
    load_dotenv()
    now = datetime.now(IST)
    state = load_json(STATE_PATH) or {}
    plan = load_json(PLAN_PATH) or {}
    track = load_json(TRACK_PATH) or {'inception': {}, 'snapshots': []}
    journal = load_json(JOURNAL_PATH) or []
    fills = read_jsonl(TRADE_LOG_PATH)
    symbols = [s for s, q in (state.get('holdings') or {}).items() if int(q) > 0]
    quotes = fetch_quotes(sorted(set(symbols) | {CORE}))
    payload = build_payload(now, state, plan, track, journal, fills, quotes)
    atomic_write_json(OUT_PATH, payload, indent=None)
    log(f"wrote {OUT_PATH} quotes_live={payload['quotes_live']}")
    print(json.dumps({'ok': True, 'quotes_live': payload['quotes_live'], 'generated': payload['generated']}))


if __name__ == '__main__':
    main()
