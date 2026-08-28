from collections.abc import Callable
from typing import Any

import numpy as np
import pandas as pd
from scipy.stats import ttest_1samp

from quantshield.config import MarketConfig
from quantshield.costs import delivery_cost
from quantshield.research.portfolio import build_weights
from quantshield.utils import log

CostFn = Callable[[pd.Series, pd.Series, float], float]

TRADING_DAYS = 252
MIN_TRAIN_DAYS = 252
STEP_DAYS = 21
MAX_CURVE_POINTS = 400
INDIA_ETF = 'NIFTYBEES.NS'


def _daily_rf(macro_close: pd.DataFrame, annual_override: float | None = None) -> float:
    if annual_override is not None:
        return annual_override / TRADING_DAYS
    if '^TNX' in macro_close.columns:
        tnx = macro_close['^TNX'].dropna()
        if len(tnx) and np.isfinite(tnx.iloc[-1]):
            return float(tnx.iloc[-1]) / 100.0 / TRADING_DAYS
    return 0.0


def _perf_stats(values: np.ndarray, daily_rf: float) -> dict[str, float]:
    rets = np.diff(values) / values[:-1]
    std = float(np.std(rets, ddof=1)) if len(rets) > 1 else 0.0
    sharpe = float(np.mean(rets - daily_rf)) / (std + 1e-10) * np.sqrt(TRADING_DAYS)
    drawdown = values / np.maximum.accumulate(values) - 1.0
    return {
        'return': round(float(values[-1] / values[0] - 1.0) * 100, 2),
        'sharpe': round(sharpe, 2),
        'vol': round(std * np.sqrt(TRADING_DAYS) * 100, 2),
        'maxdd': round(float(drawdown.min()) * 100, 2),
    }


def flat_cost(bps: float) -> CostFn:
    def cost(prev_weights: pd.Series, new_weights: pd.Series, capital: float) -> float:
        turnover = float(new_weights.sub(prev_weights, fill_value=0.0).abs().sum()) / 2.0
        return turnover * bps / 10000.0
    return cost


def india_delivery_cost(prev_weights: pd.Series, new_weights: pd.Series, capital: float) -> float:
    delta = new_weights.sub(prev_weights, fill_value=0.0) * capital
    buys = delta[delta > 0]
    sells = -delta[delta < 0]
    total = sum(delivery_cost('BUY', float(v), etf=(t == INDIA_ETF)) for t, v in buys.items())
    total += sum(delivery_cost('SELL', float(v), etf=(t == INDIA_ETF)) for t, v in sells.items())
    return float(total) / capital


def default_cost_fn(cfg: MarketConfig) -> tuple[CostFn, str]:
    if cfg.transaction_cost is None:
        label = ('NSE CNC delivery schedule per leg (STT, exchange, SEBI, stamp duty, GST, '
                 'DP charge per sell) on notional capital')
        return india_delivery_cost, label
    bps = cfg.transaction_cost * 10000.0
    return flat_cost(bps), f'flat {bps:g} bps per unit of one-way turnover'


def backtest(
    returns: pd.DataFrame,
    weights: pd.Series,
    macro_close: pd.DataFrame,
    days: int = TRADING_DAYS,
    benchmark_returns: pd.Series | None = None,
    total_capital: float = 100000,
    daily_rf: float | None = None,
) -> dict[str, Any]:
    window = returns.iloc[-days:]
    port_daily = (window * weights.reindex(window.columns, fill_value=0.0)).sum(axis=1).values
    if benchmark_returns is not None:
        bm_daily = benchmark_returns.reindex(window.index, fill_value=0.0).values
    else:
        bm_daily = np.zeros(len(window))
    port_value = total_capital * np.cumprod(np.concatenate(([1.0], 1.0 + port_daily)))
    bm_value = total_capital * np.cumprod(np.concatenate(([1.0], 1.0 + bm_daily)))

    if daily_rf is None:
        daily_rf = _daily_rf(macro_close)
    port = _perf_stats(port_value, daily_rf)
    bench = _perf_stats(bm_value, daily_rf)
    return {
        'port_return': port['return'], 'bench_return': bench['return'],
        'alpha': round(port['return'] - bench['return'], 2),
        'port_sharpe': port['sharpe'], 'bench_sharpe': bench['sharpe'],
        'port_vol': port['vol'], 'bench_vol': bench['vol'],
        'port_maxdd': port['maxdd'], 'bench_maxdd': bench['maxdd'],
        'port_final': round(float(port_value[-1])),
        'bench_final': round(float(bm_value[-1])),
        'start': window.index[0].strftime('%Y-%m-%d'),
        'end': window.index[-1].strftime('%Y-%m-%d'),
        'daily_rf': daily_rf,
    }


def bootstrap_confidence_intervals(
    monthly_returns: pd.Series,
    benchmark_returns: pd.Series,
    n_bootstrap: int = 10000,
    ci: float = 0.95,
    period_rf: float = 0.0,
) -> dict[str, Any]:
    rng = np.random.default_rng(seed=42)
    port = np.asarray(monthly_returns, dtype=float)
    bench = np.asarray(benchmark_returns, dtype=float)
    n = len(port)

    idx = rng.integers(0, n, size=(n_bootstrap, n))
    sample_port = port[idx]
    sample_bench = bench[idx]
    sharpes = (sample_port.mean(axis=1) - period_rf) / (sample_port.std(axis=1, ddof=1) + 1e-10) * np.sqrt(12)
    alphas = (sample_port - sample_bench).mean(axis=1) * 12 * 100

    tail = (1 - ci) / 2 * 100
    sharpe_lo, sharpe_hi = np.percentile(sharpes, [tail, 100 - tail])
    alpha_lo, alpha_hi = np.percentile(alphas, [tail, 100 - tail])
    return {
        'sharpe_ci': (round(float(sharpe_lo), 4), round(float(sharpe_hi), 4)),
        'alpha_ci': (round(float(alpha_lo), 4), round(float(alpha_hi), 4)),
        'alpha_includes_zero': bool(alpha_lo <= 0 <= alpha_hi),
        'n_bootstrap': n_bootstrap,
        'ci_level': ci,
    }


def _equity_curve(dates: pd.DatetimeIndex, port: np.ndarray, bench: np.ndarray) -> list[dict[str, Any]]:
    n = len(dates)
    keep = np.unique(np.linspace(0, n - 1, min(n, MAX_CURVE_POINTS)).astype(int))
    return [
        {'date': dates[i].strftime('%Y-%m-%d'), 'portfolio': round(float(port[i]), 4), 'benchmark': round(float(bench[i]), 4)}
        for i in keep
    ]


def walk_forward_backtest(
    close: pd.DataFrame,
    returns: pd.DataFrame,
    macro_close: pd.DataFrame,
    benchmark_returns: pd.Series | None,
    cfg: MarketConfig,
    detect_regime_fn: Callable[[pd.DataFrame], tuple[str, float, dict]],
    min_train_days: int = MIN_TRAIN_DAYS,
    step_days: int = STEP_DAYS,
    cost_fn: CostFn | None = None,
) -> dict[str, Any] | None:
    n = len(returns)
    if n < min_train_days + step_days:
        log(f'walk-forward skipped: {n} return rows, need {min_train_days + step_days}', 'backtest')
        return None
    if cost_fn is None:
        cost_fn, cost_model = default_cost_fn(cfg)
    else:
        cost_model = 'custom'
    daily_rf = _daily_rf(macro_close, cfg.risk_free_annual)
    equal = pd.Series(1.0 / len(returns.columns), index=returns.columns)

    prev_weights: pd.Series | None = None
    port_chunks: list[pd.Series] = []
    regimes: list[str] = []
    fallbacks = 0
    anchor = returns.index[min_train_days - 1]

    for i in range(min_train_days, n - step_days + 1, step_days):
        train_returns = returns.iloc[:i]
        train_end = train_returns.index[-1]
        train_close = close.loc[:train_end]
        train_macro = macro_close.loc[:train_end]
        train_bm = benchmark_returns.loc[:train_end] if benchmark_returns is not None else None
        test = returns.iloc[i:i + step_days]

        regime = 'unknown'
        try:
            regime, _, _ = detect_regime_fn(train_macro)
            weights, _ = build_weights(train_close, train_returns, train_macro, train_bm, cfg, regime)
            if not np.isfinite(weights.values).all() or abs(float(weights.sum()) - 1.0) > 1e-6:
                raise ValueError('non-finite or unnormalized weights')
        except Exception as exc:
            fallbacks += 1
            log(f'step {test.index[0].date()}: {exc!r}; equal weights used', 'backtest')
            weights = equal
        weights = weights.reindex(test.columns, fill_value=0.0)

        start_weights = pd.Series(0.0, index=test.columns) if prev_weights is None else prev_weights
        cost = cost_fn(start_weights, weights, cfg.notional_capital)
        growth = (1.0 + test).cumprod()
        value = (growth * weights).sum(axis=1)
        daily = value / value.shift(1).fillna(1.0) - 1.0
        daily.iloc[0] -= cost
        prev_weights = (growth.iloc[-1] * weights) / float(value.iloc[-1])
        port_chunks.append(daily)
        regimes.append(regime)

    port_daily = pd.concat(port_chunks)
    bm_daily = (
        benchmark_returns.reindex(port_daily.index, fill_value=0.0)
        if benchmark_returns is not None
        else pd.Series(0.0, index=port_daily.index)
    )
    port_values = np.concatenate(([1.0], np.cumprod(1.0 + port_daily.values)))
    bm_values = np.concatenate(([1.0], np.cumprod(1.0 + bm_daily.values)))
    port = _perf_stats(port_values, daily_rf)
    bench = _perf_stats(bm_values, daily_rf)

    period_id = np.repeat(np.arange(len(port_chunks)), step_days)
    period_port = (1.0 + port_daily).groupby(period_id).prod() - 1.0
    period_bm = (1.0 + bm_daily).groupby(period_id).prod() - 1.0
    starts = port_daily.index[::step_days]
    ends = port_daily.index[step_days - 1::step_days]
    periods = [
        {
            'period_start': starts[k].strftime('%Y-%m-%d'),
            'period_end': ends[k].strftime('%Y-%m-%d'),
            'port_return': round(float(period_port.iloc[k]) * 100, 2),
            'bench_return': round(float(period_bm.iloc[k]) * 100, 2),
            'alpha': round(float(period_port.iloc[k] - period_bm.iloc[k]) * 100, 2),
            'regime': regimes[k],
        }
        for k in range(len(port_chunks))
    ]
    alphas = (period_port - period_bm).values * 100
    win_periods = int(sum(1 for p in periods if p['alpha'] > 0))
    total_periods = len(periods)

    alpha_t_stat, alpha_p_value, alpha_significant = 0.0, 1.0, False
    if total_periods >= 2:
        t_stat, p_val = ttest_1samp(alphas, 0)
        alpha_t_stat = round(float(t_stat), 4)
        alpha_p_value = round(float(p_val), 4)
        alpha_significant = bool(p_val < 0.05)

    bootstrap_ci = (
        bootstrap_confidence_intervals(period_port, period_bm, period_rf=daily_rf * step_days)
        if total_periods >= 6 else None
    )
    curve_dates = pd.DatetimeIndex([anchor]).append(port_daily.index)

    summary = {
        'min_train_days': min_train_days,
        'step_days': step_days,
        'start': periods[0]['period_start'],
        'end': periods[-1]['period_end'],
        'total_periods': total_periods,
        'win_periods': win_periods,
        'win_rate': round(win_periods / total_periods * 100, 1),
        'fallback_periods': fallbacks,
        'cost_model': cost_model,
        'port_return': port['return'],
        'bench_return': bench['return'],
        'alpha': round(port['return'] - bench['return'], 2),
        'port_sharpe': port['sharpe'],
        'bench_sharpe': bench['sharpe'],
        'port_vol': port['vol'],
        'bench_vol': bench['vol'],
        'port_maxdd': port['maxdd'],
        'bench_maxdd': bench['maxdd'],
        'alpha_t_stat': alpha_t_stat,
        'alpha_p_value': alpha_p_value,
        'alpha_significant': alpha_significant,
        'bootstrap_ci': bootstrap_ci,
        'periods': periods,
        'equity_curve': _equity_curve(curve_dates, port_values * 100.0, bm_values * 100.0),
        'daily_returns': port_daily,
    }

    log(f"walk-forward {summary['start']} to {summary['end']}: {total_periods} periods, "
        f"{fallbacks} fallbacks, cost model: {cost_model}", 'backtest')
    log(f"alpha {summary['alpha']}% (t={alpha_t_stat}, p={alpha_p_value}), sharpe {port['sharpe']} vs "
        f"{bench['sharpe']}, maxdd {port['maxdd']}% vs {bench['maxdd']}%, win rate {summary['win_rate']}%",
        'backtest')
    return summary


def regime_conditional_performance(wf_results: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    if not wf_results or not wf_results.get('periods'):
        return {}
    frame = pd.DataFrame(wf_results['periods'])
    frame['log_port'] = np.log1p(frame['port_return'] / 100.0)
    frame['log_bench'] = np.log1p(frame['bench_return'] / 100.0)
    frame['win'] = frame['alpha'] > 0
    grouped = frame.groupby('regime')
    stats = pd.DataFrame({
        'n_months': grouped.size(),
        'total_return': (np.expm1(grouped['log_port'].sum()) * 100).round(2),
        'benchmark_return': (np.expm1(grouped['log_bench'].sum()) * 100).round(2),
        'win_rate': (grouped['win'].mean() * 100).round(1),
    })
    stats['alpha'] = (stats['total_return'] - stats['benchmark_return']).round(2)
    return {
        regime: {
            'n_months': int(row['n_months']),
            'total_return': float(row['total_return']),
            'benchmark_return': float(row['benchmark_return']),
            'alpha': float(row['alpha']),
            'win_rate': float(row['win_rate']),
        }
        for regime, row in stats.iterrows()
    }
