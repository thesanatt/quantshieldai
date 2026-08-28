from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np

from quantshield.config import INDIA, US
from quantshield.paths import PORTFOLIO
from quantshield.utils import atomic_write_json, load_json, log

TRACK_RECORD_PATH = PORTFOLIO / 'track_record.json'
SNAPSHOTS_DIR = PORTFOLIO / 'snapshots'
SNAPSHOT_KEYS = ('momentum', 'vol_adj_momentum', 'mean_reversion', 'trend', 'cross_asset', 'composite', 'weight_pct')
TRADING_DAYS = 252


def _load_track_record(path: str | Path | None = None) -> list[dict]:
    return load_json(path or TRACK_RECORD_PATH, [])


def dedupe_by_date(records: list[dict]) -> list[dict]:
    latest = {r['date']: r for r in records}
    return [latest[d] for d in sorted(latest)]


def _extract_signals_snapshot(engine_data: dict) -> dict[str, dict[str, float]]:
    return {
        row['ticker']: {k: row.get(k, 0.0) for k in SNAPSHOT_KEYS}
        for row in engine_data.get('weights', [])
    }


def _book_values(engine_data: dict, notional: float) -> tuple[float, float]:
    metrics = engine_data.get('in_sample') or {}
    port = notional * (1.0 + metrics.get('port_return', 0.0) / 100.0)
    bench = notional * (1.0 + metrics.get('bench_return', 0.0) / 100.0)
    return port, bench


def append_track_record(
    us_data: dict,
    india_data: dict | None,
    trades: list[dict],
    path: str | Path | None = None,
    usdinr: float | None = None,
) -> None:
    target = path or TRACK_RECORD_PATH
    records = _load_track_record(target)

    us_value, us_bench = _book_values(us_data, US.notional_capital)
    snapshot = _extract_signals_snapshot(us_data)
    record: dict[str, Any] = {
        'date': datetime.now().strftime('%Y-%m-%d'),
        'us_portfolio_value': round(us_value, 2),
        'india_portfolio_value': None,
        'combined_value_usd': round(us_value, 2),
        'us_benchmark_value': round(us_bench, 2),
        'india_benchmark_value': None,
        'regime_us': us_data.get('regime', {}).get('detected'),
        'regime_india': None,
        'usdinr': usdinr,
        'trades_placed': len(trades),
    }

    if india_data:
        india_value, india_bench = _book_values(india_data, INDIA.notional_capital)
        record['india_portfolio_value'] = round(india_value, 2)
        record['india_benchmark_value'] = round(india_bench, 2)
        record['regime_india'] = india_data.get('regime', {}).get('detected')
        if usdinr:
            record['combined_value_usd'] = round(us_value + india_value / usdinr, 2)
        else:
            log('usdinr not supplied; combined_value_usd covers the US book only', 'track_record')
        snapshot.update(_extract_signals_snapshot(india_data))

    record['signals_snapshot'] = snapshot
    records.append(record)
    atomic_write_json(target, records)


def save_monthly_snapshot(
    engine_output: dict,
    market: str,
    snapshots_dir: str | Path | None = None,
) -> str:
    directory = Path(snapshots_dir or SNAPSHOTS_DIR)
    now = datetime.now()
    path = directory / f"{now.strftime('%Y-%m')}-{market}.json"
    walk_forward = engine_output.get('walk_forward') or {}
    snapshot = {
        'timestamp': now.isoformat(),
        'market': market,
        'positions': engine_output.get('weights', []),
        'regime': engine_output.get('regime', {}),
        'in_sample': engine_output.get('in_sample', {}),
        'walk_forward': {k: v for k, v in walk_forward.items() if k not in ('periods', 'equity_curve')},
        'correlation': engine_output.get('correlation', {}),
        'cvar': engine_output.get('cvar', {}),
    }
    atomic_write_json(path, snapshot)
    return str(path)


def compute_live_metrics(track_record: list[dict]) -> dict[str, Any]:
    records = dedupe_by_date(track_record)
    if len(records) < 2:
        return {
            'live_sharpe': None,
            'live_alpha_annualized': None,
            'live_max_drawdown': None,
            'live_volatility': None,
            'current_drawdown': None,
            'days_since_inception': len(records),
        }

    values = np.array([r['combined_value_usd'] for r in records], dtype=float)
    bench_values = np.array([r['us_benchmark_value'] for r in records], dtype=float)
    port_returns = np.diff(values) / values[:-1]
    bench_returns = np.diff(bench_values) / bench_values[:-1]

    mean_ret = float(np.mean(port_returns))
    std_ret = float(np.std(port_returns, ddof=1)) if len(port_returns) > 1 else 1e-8
    std_ret = max(std_ret, 1e-8)
    alpha_daily = mean_ret - float(np.mean(bench_returns))

    peak = np.maximum.accumulate(values)
    drawdowns = (values - peak) / peak

    try:
        d0 = datetime.strptime(records[0]['date'], '%Y-%m-%d')
        d1 = datetime.strptime(records[-1]['date'], '%Y-%m-%d')
        days = (d1 - d0).days
    except (ValueError, KeyError):
        days = len(port_returns)

    return {
        'live_sharpe': round(mean_ret / std_ret * np.sqrt(TRADING_DAYS), 4),
        'live_alpha_annualized': round(alpha_daily * TRADING_DAYS * 100, 4),
        'live_max_drawdown': round(float(drawdowns.min()) * 100, 4),
        'live_volatility': round(std_ret * np.sqrt(TRADING_DAYS) * 100, 4),
        'current_drawdown': round(float(drawdowns[-1]) * 100, 4),
        'days_since_inception': days,
    }


def generate_monthly_report_data(track_record: list[dict], month: str) -> dict[str, Any]:
    records = dedupe_by_date(track_record)
    month_records = [r for r in records if r['date'].startswith(month)]
    if not month_records:
        return {
            'month': month,
            'monthly_return': None,
            'cumulative_return': None,
            'benchmark_return': None,
            'top_contributors': [],
            'bottom_contributors': [],
            'regime_summary': {},
            'num_trades': 0,
        }

    first, last = month_records[0], month_records[-1]
    start_val, end_val = first['combined_value_usd'], last['combined_value_usd']
    bench_start, bench_end = first['us_benchmark_value'], last['us_benchmark_value']
    inception_val = records[0]['combined_value_usd']

    regimes: dict[str, int] = {}
    for r in month_records:
        key = r.get('regime_us') or 'unknown'
        regimes[key] = regimes.get(key, 0) + 1

    first_snap = first.get('signals_snapshot', {})
    last_snap = last.get('signals_snapshot', {})
    contributions = sorted(
        (
            (ticker, round(
                (vals.get('composite', 0.0) - first_snap.get(ticker, {}).get('composite', 0.0))
                * vals.get('weight_pct', 0.0) / 100.0 * 100, 4,
            ))
            for ticker, vals in last_snap.items()
        ),
        key=lambda item: item[1], reverse=True,
    )
    as_rows = [{'ticker': t, 'contribution': c} for t, c in contributions]

    return {
        'month': month,
        'monthly_return': round((end_val / start_val - 1) * 100, 4) if start_val > 0 else 0.0,
        'cumulative_return': round((end_val / inception_val - 1) * 100, 4) if inception_val > 0 else 0.0,
        'benchmark_return': round((bench_end / bench_start - 1) * 100, 4) if bench_start > 0 else 0.0,
        'top_contributors': as_rows[:3],
        'bottom_contributors': as_rows[-3:],
        'regime_summary': regimes,
        'num_trades': sum(r.get('trades_placed', 0) for r in month_records),
    }
