import argparse
import json
import os
from datetime import datetime, timedelta

import numpy as np

from quantshield.intraday.candles import CANDLES_DIR, day_path, fetch_minute_bars, instrument_token, read_day, write_day
from quantshield.intraday.paper import NOTIONAL, SYMBOL, evaluate_session
from quantshield.intraday.stats import BOOTSTRAP_DESCRIPTION, adjusted_deltas, bootstrap_p, buy_and_hold_pct
from quantshield.paths import DASHBOARD, INTRADAY
from quantshield.utils import IST, atomic_write_json, load_json, log, now_ist

OUT_PATH = str(INTRADAY / 'orb_replay.json')
GATE_PATH = str(INTRADAY / 'gate.json')
CARD_PATH = str(DASHBOARD / 'src' / 'data' / 'orb.json')
BENCH_OPEN_DEFINITION = '09:15 bar close'
CAVEATS = [
    'in-sample single regime slice; no parameter search was run (v1 rules frozen before this replay)',
    'official candles have no intrabar sequencing: same-bar stop ambiguity resolved adversarially',
    'this is plausibility evidence only; the gate counts live paper sessions exclusively',
]


def fetch_missing(candles_dir: str, calendar_days: int) -> list[str]:
    from quantshield.broker.zerodha import _client
    kite = _client()
    token = instrument_token(kite, SYMBOL)
    if token is None:
        raise RuntimeError(f'no instrument token for {SYMBOL}')
    end = now_ist()
    by_day = fetch_minute_bars(kite, token, end - timedelta(days=calendar_days), end)
    written: list[str] = []
    for day, bars in sorted(by_day.items()):
        if not os.path.exists(day_path(SYMBOL, day, candles_dir)):
            write_day(SYMBOL, day, bars, candles_dir)
            written.append(day)
    return written


def session_days(candles_dir: str, start: str, end: str) -> list[str]:
    if not os.path.isdir(candles_dir):
        return []
    return sorted(
        d for d in os.listdir(candles_dir)
        if start <= d <= end and os.path.exists(day_path(SYMBOL, d, candles_dir))
    )


def aggregate(records: list[dict]) -> dict:
    n = len(records)
    triggered = [r for r in records if r['triggered']]
    net = np.array([r['net'] for r in triggered], dtype=float)
    gross = np.array([r['gross'] for r in triggered], dtype=float)
    costs = np.array([r['costs'] for r in triggered], dtype=float)
    wins = net[net > 0]
    losses = net[net <= 0]
    or_width = np.array([(r['or_high'] - r['or_low']) / r['or_low'] * 100 for r in records], dtype=float)
    risk = np.array([(r['entry_px'] - r['stop']) * r['qty'] for r in triggered], dtype=float)
    cost_in_r = costs / np.maximum(risk, 0.01)
    adj = adjusted_deltas(records)
    cum = np.cumsum([r['net'] for r in records])
    peak = np.maximum.accumulate(np.concatenate([[0.0], cum]))[1:]
    max_dd = float((cum - peak).min()) if n else 0.0
    avg_win = float(wins.mean()) if wins.size else 0.0
    avg_loss = float(losses.mean()) if losses.size else 0.0
    payoff = abs(avg_win / avg_loss) if avg_loss != 0 else 0.0
    breakeven_wr = 1 / (1 + payoff) * 100 if payoff > 0 else 100.0
    net_total = float(net.sum())
    hold = buy_and_hold_pct(records)
    return {
        'sessions': n,
        'date_range': [records[0]['date'], records[-1]['date']] if n else [],
        'triggered': len(triggered),
        'trigger_rate_pct': round(len(triggered) / n * 100, 1) if n else 0.0,
        'wins': int(wins.size),
        'win_rate_pct': round(wins.size / len(triggered) * 100, 1) if triggered else None,
        'avg_win_rs': round(avg_win, 2),
        'avg_loss_rs': round(avg_loss, 2),
        'payoff_ratio': round(payoff, 2),
        'breakeven_win_rate_pct': round(breakeven_wr, 1),
        'gross_total_rs': round(float(gross.sum()), 2),
        'net_total_rs': round(net_total, 2),
        'net_per_session_rs': round(net_total / n, 3) if n else 0.0,
        'total_costs_rs': round(float(costs.sum()), 2),
        'max_drawdown_rs': round(max_dd, 2),
        'strategy_total_ret_pct': round(net_total / NOTIONAL * 100, 2),
        'bench_open_definition': BENCH_OPEN_DEFINITION,
        'bench_cum_daily_pct': round(float(np.sum([r['bench_ret_pct'] for r in records])), 2),
        'bench_hold_ret_pct': round(hold, 2) if hold is not None else None,
        'or_width_pct_median': round(float(np.median(or_width)), 3) if n else None,
        'or_width_pct_p25_p75': [round(float(np.percentile(or_width, q)), 3) for q in (25, 75)] if n else [],
        'cost_in_r_median': round(float(np.median(cost_in_r)), 3) if cost_in_r.size else None,
        'adjusted_delta_mean_pct': round(float(adj.mean()), 4) if adj.size else None,
        'adjusted_delta_std_pct': round(float(adj.std(ddof=1)), 4) if adj.size > 1 else None,
        'bootstrap_p_one_sided': round(bootstrap_p(adj), 4),
        'test': BOOTSTRAP_DESCRIPTION,
    }


def replay(candles_dir: str, start: str, end: str) -> dict:
    records: list[dict] = []
    skipped: list[str] = []
    for day in session_days(candles_dir, start, end):
        record = evaluate_session(read_day(SYMBOL, day, candles_dir), day)
        if record is None:
            skipped.append(day)
        else:
            records.append(record)
    summary = aggregate(records)
    summary['skipped_days'] = skipped
    summary['caveats'] = CAVEATS
    return {'generated': datetime.now(IST).isoformat(), 'summary': summary, 'records': records}


def verification_amendment(summary: dict) -> dict:
    return {
        'date': now_ist().strftime('%Y-%m-%d'),
        'type': 'verification',
        'task': 'orb_geometry_replay',
        'note': 'In-sample cost-geometry replay on official 1-min candles via frozen evaluate_session. '
                'Not the gate test; live paper sessions remain the only gate evidence.',
        'results': summary,
    }


def append_amendment(entry: dict, gate_path: str = GATE_PATH) -> None:
    gate = load_json(gate_path, {}) or {}
    gate.setdefault('amendments', []).append(entry)
    atomic_write_json(gate_path, gate)


def dashboard_card(out: dict, gate: dict) -> dict:
    s = out['summary']
    sign = 'negative' if s['net_total_rs'] < 0 else 'positive'
    verdict = f"Gate {str(gate.get('status', 'unknown')).lower()}, {sign} after costs"
    benchmark_note = (
        f"Session benchmark is the same-capital NIFTYBEES return from the {BENCH_OPEN_DEFINITION} to the last bar "
        f"close, weighted by time in market; the 09:15 bar open is the pre-open auction print and is not used. "
        f"Summed session returns over the window: {s['bench_cum_daily_pct']}%; buy-and-hold from the first "
        f"session open to the last session close: {s['bench_hold_ret_pct']}%."
    )
    return {
        'registered': str(gate.get('registered', ''))[:10],
        'sessions': s['sessions'],
        'triggered': s['triggered'],
        'wins': s['wins'],
        'win_rate_pct': s['win_rate_pct'],
        'breakeven_win_rate_pct': s['breakeven_win_rate_pct'],
        'gross': s['gross_total_rs'],
        'costs': s['total_costs_rs'],
        'net': s['net_total_rs'],
        'max_drawdown': s['max_drawdown_rs'],
        'bootstrap_p': s['bootstrap_p_one_sided'],
        'notional': int(NOTIONAL),
        'verdict': verdict,
        'benchmark_note': benchmark_note,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--candles-dir', default=CANDLES_DIR)
    parser.add_argument('--fetch', action='store_true')
    parser.add_argument('--days', type=int, default=200)
    parser.add_argument('--start', default='2000-01-01')
    parser.add_argument('--end', default=(now_ist() - timedelta(days=1)).strftime('%Y-%m-%d'))
    parser.add_argument('--out', default=OUT_PATH)
    parser.add_argument('--gate', default=GATE_PATH)
    parser.add_argument('--amend', action='store_true')
    parser.add_argument('--dashboard', action='store_true')
    args = parser.parse_args()
    if args.fetch:
        written = fetch_missing(args.candles_dir, args.days)
        log(f'wrote {len(written)} new session files', 'replay')
    out = replay(args.candles_dir, args.start, args.end)
    if not out['records']:
        log('no sessions found under the candles directory; nothing written', 'replay')
        raise SystemExit(2)
    atomic_write_json(args.out, out)
    if args.amend:
        append_amendment(verification_amendment(out['summary']), args.gate)
    if args.dashboard:
        atomic_write_json(CARD_PATH, dashboard_card(out, load_json(args.gate, {}) or {}))
    print(json.dumps(out['summary'], indent=2))


if __name__ == '__main__':
    main()
