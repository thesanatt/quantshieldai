from collections.abc import Sequence

import numpy as np

BOOTSTRAP_N = 10000
BOOTSTRAP_SEED = 20260721
BOOTSTRAP_DESCRIPTION = (
    'one-sided percentile bootstrap of the mean adjusted delta: fraction of '
    f'{BOOTSTRAP_N} resampled means at or below zero (seed {BOOTSTRAP_SEED}); '
    'small values favour mean > 0'
)


def adjusted_deltas(records: list[dict]) -> np.ndarray:
    strat = np.array([r['strat_ret_pct'] for r in records], dtype=float)
    exposure = np.array([r['time_in_market_frac'] for r in records], dtype=float)
    bench = np.array([r['bench_ret_pct'] for r in records], dtype=float)
    return strat - exposure * bench


def bootstrap_p(deltas: Sequence[float] | np.ndarray, n: int = BOOTSTRAP_N, seed: int = BOOTSTRAP_SEED) -> float:
    arr = np.asarray(deltas, dtype=float)
    if arr.size < 3:
        return 1.0
    rng = np.random.default_rng(seed)
    means = rng.choice(arr, size=(n, arr.size), replace=True).mean(axis=1)
    return float((means <= 0).mean())


def buy_and_hold_pct(records: list[dict]) -> float | None:
    ordered = sorted(records, key=lambda r: r['date'])
    if not ordered:
        return None
    first = ordered[0].get('bench_open')
    last = ordered[-1].get('bench_close')
    if not first or not last:
        return None
    return (last / first - 1) * 100
