import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import os

import numpy as np
import pandas as pd
import yfinance as yf
from scipy.stats import ttest_rel
from datetime import datetime, timedelta

from quantshield.config import (
    TICKERS, BENCHMARK_TICKER, MACRO_TICKERS, TOTAL_CAPITAL,
    REGIME_WEIGHTS, TILT_STRENGTH, MIN_WEIGHT, MAX_WEIGHT, US_SECTOR_MAP, INDIA_TICKERS,
    INDIA_MACRO_TICKERS, INDIA_TOTAL_CAPITAL, INDIA_REGIME_WEIGHTS,
    INDIA_SECTOR_MAP, INDIA_TILT_STRENGTH, INDIA_MIN_WEIGHT, INDIA_MAX_WEIGHT,
)
from legacy_signals import (
    VOL_SCALAR_MAX, VOL_SCALAR_MIN, VOL_TARGET_INDIA, VOL_TARGET_US,
    apply_sector_limits_wf, compute_transaction_cost, copper_gold_signal, vix_term_structure_signal, vol_target,
)
from quantshield.risk.cvar import apply_cvar_constraint
from quantshield.risk.position_limits import apply_position_limits
from quantshield.signals.regime import us_detect_regime, india_detect_regime
from quantshield.research.backtest import walk_forward_backtest
from quantshield.utils import log


def download_data(tickers, macro_tickers, benchmark, days=3650):
    end = datetime.now()
    start = end - timedelta(days=days)
    start_str = start.strftime('%Y-%m-%d')
    end_str = end.strftime('%Y-%m-%d')

    log(f"Downloading {len(tickers)} tickers from {start_str} to {end_str}")
    all_tickers = tickers + [benchmark] + macro_tickers
    raw = yf.download(all_tickers, start=start_str, end=end_str, auto_adjust=True, progress=False)

    close = raw['Close'][tickers].dropna(how='all')
    volume = raw['Volume'][tickers].dropna(how='all')
    benchmark_close = raw['Close'][benchmark].dropna()

    macro_cols = [t for t in macro_tickers if t in raw['Close'].columns]
    macro_close = raw['Close'][macro_cols].ffill()

    close = close.ffill().dropna()
    volume = volume.reindex(close.index).fillna(0)
    benchmark_close = benchmark_close.reindex(close.index).ffill()

    returns = close.pct_change().dropna()
    benchmark_returns = benchmark_close.pct_change().dropna()

    common_idx = returns.index.intersection(benchmark_returns.index)
    returns = returns.loc[common_idx]
    benchmark_returns = benchmark_returns.loc[common_idx]
    close = close.loc[close.index.isin(returns.index) | (close.index == returns.index[0] - pd.Timedelta(days=5))]
    close = close.reindex(returns.index.insert(0, close.index[0])).ffill().iloc[1:]
    close = close.reindex(returns.index).ffill()
    volume = volume.reindex(returns.index).fillna(0)

    log(f"  Data: {len(returns)} trading days, {len(returns.columns)} stocks")
    return close, returns, volume, benchmark_returns, macro_close


def compute_transaction_cost_for_turnover(
    weight_changes, volume_data, close_data, returns_data,
    spread_bps=5.0, impact_k=0.1, total_capital=100000
):
    return compute_transaction_cost(
        weight_changes, volume_data, close_data, returns_data,
        spread_bps=spread_bps, impact_k=impact_k, total_capital=total_capital,
    )


def run_strategy_a(returns, close, volume, benchmark_returns, total_capital):
    log("Running Strategy A: Naive Equal Weight")
    n_stocks = len(returns.columns)
    equal_w = pd.Series(1.0 / n_stocks, index=returns.columns)

    start_idx = 252
    step_size = 21
    portfolio_values = [total_capital]
    benchmark_values = [total_capital]
    test_dates = []
    prev_weights = None
    monthly_port_rets = []
    monthly_bm_rets = []
    turnovers = []

    i = start_idx
    while i + step_size <= len(returns):
        test_returns = returns.iloc[i:i + step_size]
        if len(test_returns) == 0:
            break

        current_weights = equal_w.copy()

        turnover_cost = 0.0
        if prev_weights is not None:
            weight_changes = current_weights - prev_weights
            train_vol = volume.iloc[:i]
            train_close = close.iloc[:i]
            train_ret = returns.iloc[:i]
            turnover_cost = compute_transaction_cost_for_turnover(
                weight_changes, train_vol, train_close, train_ret,
                total_capital=total_capital,
            )
            turnovers.append(float(weight_changes.abs().sum()))
        prev_weights = current_weights.copy()

        port_daily = (test_returns * current_weights).sum(axis=1).values.copy()
        port_daily[0] -= turnover_cost

        bm_daily = benchmark_returns.reindex(test_returns.index, fill_value=0.0).values

        for j in range(len(test_returns)):
            portfolio_values.append(portfolio_values[-1] * (1 + port_daily[j]))
            benchmark_values.append(benchmark_values[-1] * (1 + bm_daily[j]))
            test_dates.append(test_returns.index[j])

        period_port_ret = (portfolio_values[-1] / portfolio_values[-len(test_returns) - 1]) - 1
        period_bm_ret = (benchmark_values[-1] / benchmark_values[-len(test_returns) - 1]) - 1
        monthly_port_rets.append(period_port_ret)
        monthly_bm_rets.append(period_bm_ret)

        i += step_size

    return _build_results(
        portfolio_values, benchmark_values, test_dates,
        monthly_port_rets, monthly_bm_rets, turnovers, "A_EqualWeight"
    )


def run_strategy_b(
    returns, close, volume, benchmark_returns, macro_close, total_capital,
    sector_map, vol_target_val, detect_regime_fn,
    max_sector_pct=0.40, max_single_stock=0.25, max_portfolio_beta=1.5,
    max_monthly_cvar=0.03, cvar_confidence=0.95,
):
    log("Running Strategy B: Equal Weight + Risk Management Stack")
    n_stocks = len(returns.columns)

    start_idx = 252
    portfolio_values = [total_capital]
    benchmark_values = [total_capital]
    test_dates = []
    prev_weights = None
    monthly_port_rets = []
    monthly_bm_rets = []
    turnovers = []
    last_rebalance_idx = None

    i = start_idx
    while i < len(returns):
        train_returns = returns.iloc[:i]
        train_close = close.iloc[:i]
        train_macro = macro_close.loc[macro_close.index <= train_close.index[-1]]

        try:
            regime, _, _ = detect_regime_fn(train_macro)
        except Exception:
            regime = 'risk_on'

        if regime == 'crisis':
            step_size = 5
        elif regime == 'risk_off':
            step_size = 10
        else:
            step_size = 21

        if i + step_size > len(returns):
            step_size = len(returns) - i
        if step_size <= 0:
            break

        test_returns = returns.iloc[i:i + step_size]
        if len(test_returns) == 0:
            break

        equal_w = pd.Series(1.0 / n_stocks, index=returns.columns)

        adjusted = vol_target(
            train_returns, equal_w,
            target_vol=vol_target_val,
            scalar_min=VOL_SCALAR_MIN, scalar_max=VOL_SCALAR_MAX,
        )

        if sector_map:
            adjusted = apply_sector_limits_wf(adjusted, sector_map, max_sector_pct)

        adjusted, _ = apply_position_limits(
            adjusted, train_returns, benchmark_returns=benchmark_returns,
            max_single_stock=max_single_stock, max_portfolio_beta=max_portfolio_beta,
        )

        adjusted = apply_cvar_constraint(
            adjusted, train_returns,
            max_monthly_cvar=max_monthly_cvar, confidence=cvar_confidence,
        )

        adjusted = adjusted / adjusted.sum()

        turnover_cost = 0.0
        if prev_weights is not None:
            all_tickers = adjusted.index.union(prev_weights.index)
            weight_changes = adjusted.reindex(all_tickers, fill_value=0).sub(
                prev_weights.reindex(all_tickers, fill_value=0)
            )
            train_vol = volume.iloc[:i]
            turnover_cost = compute_transaction_cost_for_turnover(
                weight_changes, train_vol, train_close, train_returns,
                total_capital=total_capital,
            )
            turnovers.append(float(weight_changes.abs().sum()))
        prev_weights = adjusted.copy()

        port_daily = (test_returns * adjusted).sum(axis=1).values.copy()
        port_daily[0] -= turnover_cost

        bm_daily = benchmark_returns.reindex(test_returns.index, fill_value=0.0).values

        for j in range(len(test_returns)):
            portfolio_values.append(portfolio_values[-1] * (1 + port_daily[j]))
            benchmark_values.append(benchmark_values[-1] * (1 + bm_daily[j]))
            test_dates.append(test_returns.index[j])

        period_port_ret = (portfolio_values[-1] / portfolio_values[-len(test_returns) - 1]) - 1
        period_bm_ret = (benchmark_values[-1] / benchmark_values[-len(test_returns) - 1]) - 1
        monthly_port_rets.append(period_port_ret)
        monthly_bm_rets.append(period_bm_ret)

        i += step_size

    return _build_results(
        portfolio_values, benchmark_values, test_dates,
        monthly_port_rets, monthly_bm_rets, turnovers, "B_EW_RiskMgmt"
    )


def run_strategy_c(
    close, returns, volume, benchmark_returns, macro_close, total_capital,
    tilt_strength, min_weight, max_weight, regime_weights, detect_regime_fn,
    cross_asset_fn, vix_ts_fn, copper_gold_fn, sector_map, max_sector_pct=0.40,
    max_monthly_cvar=0.03, cvar_confidence=0.95,
    max_single_stock=0.25, max_portfolio_beta=1.5, spread_bps=5.0,
):
    log("Running Strategy C: Full Engine")

    result = walk_forward_backtest(
        close=close, returns=returns, macro_close=macro_close,
        benchmark_returns=benchmark_returns,
        train_months=12, test_months=1,
        transaction_cost_bps=10,
        total_capital=total_capital,
        tilt_strength=tilt_strength,
        min_weight=min_weight,
        max_weight=max_weight,
        regime_weights=regime_weights,
        detect_regime_fn=detect_regime_fn,
        cross_asset_fn=cross_asset_fn,
        vix_ts_fn=vix_ts_fn,
        copper_gold_fn=copper_gold_fn,
        daily_rf=None,
        volume_data=volume,
        spread_bps=spread_bps,
        sector_map=sector_map,
        max_sector_pct=max_sector_pct,
        max_monthly_cvar=max_monthly_cvar,
        cvar_confidence=cvar_confidence,
        max_single_stock=max_single_stock,
        max_portfolio_beta=max_portfolio_beta,
    )
    return result


def _build_results(portfolio_values, benchmark_values, test_dates,
                   monthly_port_rets, monthly_bm_rets, turnovers, name):
    pv = np.array(portfolio_values)
    bv = np.array(benchmark_values)

    daily_port_rets = np.diff(pv) / pv[:-1]
    daily_bm_rets = np.diff(bv) / bv[:-1]

    ann_ret = (pv[-1] / pv[0]) ** (252.0 / len(daily_port_rets)) - 1
    ann_vol = np.std(daily_port_rets, ddof=1) * np.sqrt(252)
    sharpe = ann_ret / (ann_vol + 1e-10)

    running_max = np.maximum.accumulate(pv)
    drawdowns = pv / running_max - 1
    max_dd = float(np.min(drawdowns))

    monthly_rets_arr = np.array(monthly_port_rets)
    if len(monthly_rets_arr) >= 5:
        monthly_arr_scaled = monthly_rets_arr * np.sqrt(21)
        sorted_monthly = np.sort(monthly_rets_arr)
        cutoff = max(1, int(len(sorted_monthly) * 0.05))
        cvar_95 = float(np.mean(sorted_monthly[:cutoff]))
    else:
        cvar_95 = 0.0

    worst_dd_idx = np.argmin(drawdowns)
    peak_idx = np.argmax(pv[:worst_dd_idx + 1])
    recovery_idx = None
    peak_val = pv[peak_idx]
    for k in range(worst_dd_idx, len(pv)):
        if pv[k] >= peak_val:
            recovery_idx = k
            break
    if recovery_idx is not None:
        recovery_days = recovery_idx - peak_idx
    else:
        recovery_days = len(pv) - peak_idx

    dd_adj_ret = ann_ret / abs(max_dd) if abs(max_dd) > 1e-10 else 0.0

    avg_turnover = float(np.mean(turnovers)) if turnovers else 0.0

    dates_series = pd.DatetimeIndex(test_dates) if test_dates else pd.DatetimeIndex([])

    return {
        'name': name,
        'portfolio_values': pv,
        'benchmark_values': bv,
        'dates': dates_series,
        'ann_return': float(ann_ret),
        'ann_vol': float(ann_vol),
        'sharpe': float(sharpe),
        'max_dd': float(max_dd),
        'cvar_95': float(cvar_95),
        'recovery_days': recovery_days,
        'dd_adj_return': float(dd_adj_ret),
        'avg_turnover': avg_turnover,
        'monthly_port_rets': monthly_port_rets,
        'monthly_bm_rets': monthly_bm_rets,
        'daily_port_rets': daily_port_rets,
    }


def convert_wf_to_results(wf_result, name="C_FullEngine", total_capital=100000):
    if wf_result is None:
        return None

    periods = wf_result['periods']
    monthly_port = [p['port_return'] / 100.0 for p in periods]
    monthly_bm = [p['voo_return'] / 100.0 for p in periods]

    pv = [total_capital]
    for p in periods:
        month_ret = p['port_return'] / 100.0
        for _ in range(21):
            daily_r = (1 + month_ret) ** (1.0 / 21) - 1
            pv.append(pv[-1] * (1 + daily_r))

    pv = np.array(pv)
    daily_rets = np.diff(pv) / pv[:-1]

    ann_ret = (pv[-1] / pv[0]) ** (252.0 / max(len(daily_rets), 1)) - 1
    ann_vol = np.std(daily_rets, ddof=1) * np.sqrt(252) if len(daily_rets) > 1 else 0
    sharpe = wf_result['port_sharpe']

    max_dd = wf_result['port_maxdd'] / 100.0

    sorted_monthly = np.sort(monthly_port)
    cutoff = max(1, int(len(sorted_monthly) * 0.05))
    cvar_95 = float(np.mean(sorted_monthly[:cutoff])) if len(sorted_monthly) >= 5 else 0.0

    dd_adj_ret = ann_ret / abs(max_dd) if abs(max_dd) > 1e-10 else 0.0

    return {
        'name': name,
        'ann_return': float(ann_ret),
        'sharpe': float(sharpe),
        'max_dd': float(max_dd),
        'cvar_95': float(cvar_95),
        'dd_adj_return': float(dd_adj_ret),
        'monthly_port_rets': monthly_port,
        'monthly_bm_rets': monthly_bm,
        'wf_raw': wf_result,
    }


def stress_test(portfolio_values, dates, start_date, end_date, label):
    if len(dates) == 0:
        return {'label': label, 'available': False}

    mask = (dates >= pd.Timestamp(start_date)) & (dates <= pd.Timestamp(end_date))
    if mask.sum() == 0:
        return {'label': label, 'available': False}

    idx_in_pv = np.where(mask)[0]
    start_pv_idx = idx_in_pv[0] + 1
    end_pv_idx = idx_in_pv[-1] + 1

    pv_slice = portfolio_values[start_pv_idx:end_pv_idx + 1]
    if len(pv_slice) < 2:
        return {'label': label, 'available': False}

    period_return = pv_slice[-1] / pv_slice[0] - 1
    peak = np.maximum.accumulate(pv_slice)
    worst_dd = float(np.min(pv_slice / peak - 1))

    trough_idx = np.argmin(pv_slice / peak)
    peak_val = pv_slice[0]
    recovery_days = None
    for k in range(trough_idx, len(pv_slice)):
        if pv_slice[k] >= peak_val:
            recovery_days = k - trough_idx
            break

    return {
        'label': label,
        'available': True,
        'return': float(period_return),
        'worst_dd': float(worst_dd),
        'recovery_days': recovery_days,
        'n_days': len(pv_slice),
    }


def aligned_monthly_returns(pv_a, dates_a, pv_b, dates_b):
    ser_a = pd.Series(pv_a[1:], index=dates_a)
    ser_b = pd.Series(pv_b[1:], index=dates_b)
    common_dates = ser_a.index.intersection(ser_b.index)
    if len(common_dates) < 42:
        return np.array([]), np.array([])
    ser_a = ser_a.reindex(common_dates)
    ser_b = ser_b.reindex(common_dates)

    month_ends = []
    for i in range(1, len(common_dates)):
        if common_dates[i].month != common_dates[i - 1].month:
            month_ends.append(i - 1)
    month_ends.append(len(common_dates) - 1)

    rets_a = []
    rets_b = []
    prev = 0
    for me in month_ends:
        if me <= prev:
            continue
        ra = ser_a.iloc[me] / ser_a.iloc[prev] - 1
        rb = ser_b.iloc[me] / ser_b.iloc[prev] - 1
        rets_a.append(ra)
        rets_b.append(rb)
        prev = me

    return np.array(rets_a), np.array(rets_b)


def bootstrap_sharpe_diff(monthly_a, monthly_b, n_bootstrap=10000, seed=42):
    rng = np.random.default_rng(seed=seed)
    a = np.array(monthly_a)
    b = np.array(monthly_b)
    n = min(len(a), len(b))
    a = a[:n]
    b = b[:n]

    diffs = np.empty(n_bootstrap)
    for i in range(n_bootstrap):
        idx = rng.integers(0, n, size=n)
        sa = a[idx]
        sb = b[idx]
        sharpe_a = np.mean(sa) / (np.std(sa, ddof=1) + 1e-10) * np.sqrt(12)
        sharpe_b = np.mean(sb) / (np.std(sb, ddof=1) + 1e-10) * np.sqrt(12)
        diffs[i] = sharpe_b - sharpe_a

    lo = float(np.percentile(diffs, 2.5))
    hi = float(np.percentile(diffs, 97.5))
    includes_zero = bool(lo <= 0 <= hi)
    median_diff = float(np.median(diffs))

    return {
        'ci_lo': round(lo, 4),
        'ci_hi': round(hi, 4),
        'median_diff': round(median_diff, 4),
        'includes_zero': includes_zero,
    }


def run_universe(universe_name, tickers, benchmark_ticker, macro_tickers,
                 total_capital, sector_map, regime_weights, detect_regime_fn,
                 vol_target_val, tilt_strength, min_weight, max_weight,
                 max_sector_pct=0.40):
    log(f"\n{'='*60}")
    log(f"UNIVERSE: {universe_name}")
    log(f"{'='*60}")

    close, returns, volume, benchmark_returns, macro_close = download_data(
        tickers, macro_tickers, benchmark_ticker
    )

    result_a = run_strategy_a(returns, close, volume, benchmark_returns, total_capital)

    result_b = run_strategy_b(
        returns, close, volume, benchmark_returns, macro_close, total_capital,
        sector_map=sector_map, vol_target_val=vol_target_val,
        detect_regime_fn=detect_regime_fn, max_sector_pct=max_sector_pct,
    )

    try:
        from quantshield.signals.cross_asset import us_cross_asset_signals
        ca_fn = us_cross_asset_signals
        vix_fn = vix_term_structure_signal
        cg_fn = copper_gold_signal
    except ImportError:
        ca_fn = None
        vix_fn = None
        cg_fn = None

    wf_result = run_strategy_c(
        close, returns, volume, benchmark_returns, macro_close, total_capital,
        tilt_strength=tilt_strength, min_weight=min_weight, max_weight=max_weight,
        regime_weights=regime_weights, detect_regime_fn=detect_regime_fn,
        cross_asset_fn=ca_fn, vix_ts_fn=vix_fn, copper_gold_fn=cg_fn,
        sector_map=sector_map, max_sector_pct=max_sector_pct,
        spread_bps=5.0,
    )

    result_c = convert_wf_to_results(wf_result, total_capital=total_capital)

    covid_a = stress_test(result_a['portfolio_values'], result_a['dates'],
                          '2020-02-19', '2020-03-23', 'COVID crash')
    covid_b = stress_test(result_b['portfolio_values'], result_b['dates'],
                          '2020-02-19', '2020-03-23', 'COVID crash')

    bear22_a = stress_test(result_a['portfolio_values'], result_a['dates'],
                           '2022-01-03', '2022-10-12', '2022 bear market')
    bear22_b = stress_test(result_b['portfolio_values'], result_b['dates'],
                           '2022-01-03', '2022-10-12', '2022 bear market')

    aligned_a, aligned_b = aligned_monthly_returns(
        result_a['portfolio_values'], result_a['dates'],
        result_b['portfolio_values'], result_b['dates'],
    )
    n_common = len(aligned_a)
    log(f"  Aligned monthly returns: {n_common} months for A vs B comparison")

    boot_ab = bootstrap_sharpe_diff(aligned_a.tolist(), aligned_b.tolist())

    boot_ac = None
    boot_bc = None
    if result_c is not None:
        boot_ac = bootstrap_sharpe_diff(
            result_a['monthly_port_rets'], result_c['monthly_port_rets']
        )
        boot_bc = bootstrap_sharpe_diff(
            result_b['monthly_port_rets'], result_c['monthly_port_rets']
        )

    if n_common >= 3:
        t_stat_ab, p_val_ab = ttest_rel(aligned_a, aligned_b)
    else:
        t_stat_ab, p_val_ab = 0.0, 1.0

    t_stat_ac, p_val_ac = 0.0, 1.0
    t_stat_bc, p_val_bc = 0.0, 1.0
    if result_c is not None:
        n_ac = min(len(result_a['monthly_port_rets']), len(result_c['monthly_port_rets']))
        if n_ac >= 3:
            t_stat_ac, p_val_ac = ttest_rel(
                result_a['monthly_port_rets'][:n_ac],
                result_c['monthly_port_rets'][:n_ac],
            )
        n_bc = min(len(result_b['monthly_port_rets']), len(result_c['monthly_port_rets']))
        if n_bc >= 3:
            t_stat_bc, p_val_bc = ttest_rel(
                result_b['monthly_port_rets'][:n_bc],
                result_c['monthly_port_rets'][:n_bc],
            )

    corr_ab = float(np.corrcoef(aligned_a, aligned_b)[0, 1]) if n_common >= 3 else 0.0

    return {
        'universe': universe_name,
        'result_a': result_a,
        'result_b': result_b,
        'result_c': result_c,
        'stress': {
            'covid_a': covid_a, 'covid_b': covid_b,
            'bear22_a': bear22_a, 'bear22_b': bear22_b,
        },
        'bootstrap': {
            'a_vs_b': boot_ab, 'a_vs_c': boot_ac, 'b_vs_c': boot_bc,
        },
        'paired_ttest': {
            'a_vs_b': {'t_stat': float(t_stat_ab), 'p_value': float(p_val_ab)},
            'a_vs_c': {'t_stat': float(t_stat_ac), 'p_value': float(p_val_ac)},
            'b_vs_c': {'t_stat': float(t_stat_bc), 'p_value': float(p_val_bc)},
        },
        'monthly_corr_ab': corr_ab,
        'n_months': n_common,
    }


def fmt_pct(val, decimals=2):
    return f"{val * 100:.{decimals}f}%"


def fmt_num(val, decimals=2):
    return f"{val:.{decimals}f}"


def write_report(us_results, india_results, output_path):
    lines = []
    def w(s=""):
        lines.append(s)

    w("# The Existential Experiment: Does the Risk Management Stack Add Value?")
    w()
    w(f"**Date:** {datetime.now().strftime('%Y-%m-%d')}")
    w()
    w("## Hypothesis")
    w()
    w("An earlier lookback sweep showed that momentum tilts do not beat naive equal weight.")
    w("The full engine (signals + HRP + risk management) produced Sharpe ~0.966 versus ~1.011")
    w("for 1/N equal weight. This experiment isolates the question: does the risk management")
    w("stack alone (vol targeting, sector limits, position limits, CVaR constraint, regime-adaptive")
    w("rebalancing) add measurable value on top of equal weight?")
    w()
    w("## Methodology")
    w()
    w("Three strategies compared head-to-head on identical data and time periods:")
    w()
    w("**Strategy A (Naive Equal Weight):** 1/N weights, monthly rebalance, realistic transaction costs.")
    w("This is the baseline anyone can replicate for free with a brokerage account.")
    w()
    w("**Strategy B (Equal Weight + Risk Management):** Start with 1/N weights, then apply the full")
    w("risk management stack in production order:")
    w("1. Vol targeting (target=15% US / 20% India, 63-day window, scalar clipped 0.5-1.5)")
    w("2. Sector exposure limits (40% max per sector)")
    w("3. Position limits (25% max single stock, 1.5 max portfolio beta)")
    w("4. CVaR constraint (3% max monthly CVaR at 95% confidence)")
    w("5. Regime-adaptive rebalancing frequency (crisis=weekly, risk_off=biweekly, risk_on=monthly)")
    w("6. Same transaction cost model as A (spread 5bps + sqrt impact model)")
    w()
    w("**Strategy C (Full Engine):** All signals (momentum, vol-adj momentum, RSI, trend, cross-asset,")
    w("VIX term structure, copper-gold) + HRP weights + signal tilting + full risk management stack.")
    w("This is the current production engine.")
    w()
    w("**Data:** Maximum available history via yfinance (~10 years). Walk-forward with 12-month")
    w("training window, rolling monthly test periods. Transaction costs use spread + sqrt market")
    w("impact model (spread_bps=5, impact_k=0.1).")
    w()
    w("**Statistical Tests:** Bootstrap 95% CI on Sharpe difference (10,000 resamples on monthly")
    w("returns to avoid autocorrelation). Paired t-test on monthly return differences as secondary check.")
    w()

    for res in [us_results, india_results]:
        if res is None:
            continue
        universe = res['universe']
        ra = res['result_a']
        rb = res['result_b']
        rc = res['result_c']

        w(f"## {universe} Results")
        w()
        w(f"**Test period:** {res['n_months']} monthly periods")
        w()

        w("### Performance Summary")
        w()
        w("| Metric | A: Equal Weight | B: EW + Risk Mgmt | C: Full Engine |")
        w("|-|-|-|-|")

        c_ann = fmt_pct(rc['ann_return']) if rc else "N/A"
        c_sharpe = fmt_num(rc['sharpe']) if rc else "N/A"
        c_maxdd = fmt_pct(rc['max_dd']) if rc else "N/A"
        c_cvar = fmt_pct(rc['cvar_95']) if rc else "N/A"
        c_ddar = fmt_num(rc['dd_adj_return']) if rc else "N/A"

        w(f"| Ann. Return (after costs) | {fmt_pct(ra['ann_return'])} | {fmt_pct(rb['ann_return'])} | {c_ann} |")
        w(f"| Ann. Volatility | {fmt_pct(ra['ann_vol'])} | {fmt_pct(rb['ann_vol'])} | N/A |")
        w(f"| Sharpe Ratio | {fmt_num(ra['sharpe'])} | {fmt_num(rb['sharpe'])} | {c_sharpe} |")
        w(f"| Max Drawdown | {fmt_pct(ra['max_dd'])} | {fmt_pct(rb['max_dd'])} | {c_maxdd} |")
        w(f"| Monthly CVaR (95%) | {fmt_pct(ra['cvar_95'])} | {fmt_pct(rb['cvar_95'])} | {c_cvar} |")
        w(f"| Longest Recovery (days) | {ra['recovery_days']} | {rb['recovery_days']} | N/A |")
        w(f"| DD-Adjusted Return | {fmt_num(ra['dd_adj_return'])} | {fmt_num(rb['dd_adj_return'])} | {c_ddar} |")
        w(f"| Avg Turnover/Rebalance | {fmt_pct(ra['avg_turnover'])} | {fmt_pct(rb['avg_turnover'])} | N/A |")
        w(f"| Monthly Return Corr (A vs B) | {fmt_num(res['monthly_corr_ab'])} | - | - |")
        w()

        w("### Stress Tests")
        w()
        w("| Event | A: Return | A: Worst DD | B: Return | B: Worst DD |")
        w("|-|-|-|-|-|")

        for event_key in ['covid', 'bear22']:
            sa = res['stress'][f'{event_key}_a']
            sb = res['stress'][f'{event_key}_b']
            if sa['available'] and sb['available']:
                w(f"| {sa['label']} | {fmt_pct(sa['return'])} | {fmt_pct(sa['worst_dd'])} | {fmt_pct(sb['return'])} | {fmt_pct(sb['worst_dd'])} |")
            else:
                w(f"| {sa['label']} | Data unavailable | - | Data unavailable | - |")
        w()

        w("### Statistical Tests")
        w()
        w("#### Bootstrap 95% CI on Sharpe Difference (10,000 resamples)")
        w()
        w("| Comparison | CI Lower | CI Upper | Median Diff | Includes Zero? |")
        w("|-|-|-|-|-|")

        bab = res['bootstrap']['a_vs_b']
        w(f"| B - A | {fmt_num(bab['ci_lo'], 4)} | {fmt_num(bab['ci_hi'], 4)} | {fmt_num(bab['median_diff'], 4)} | {'YES' if bab['includes_zero'] else 'NO'} |")

        if res['bootstrap']['a_vs_c']:
            bac = res['bootstrap']['a_vs_c']
            w(f"| C - A | {fmt_num(bac['ci_lo'], 4)} | {fmt_num(bac['ci_hi'], 4)} | {fmt_num(bac['median_diff'], 4)} | {'YES' if bac['includes_zero'] else 'NO'} |")

        if res['bootstrap']['b_vs_c']:
            bbc = res['bootstrap']['b_vs_c']
            w(f"| C - B | {fmt_num(bbc['ci_lo'], 4)} | {fmt_num(bbc['ci_hi'], 4)} | {fmt_num(bbc['median_diff'], 4)} | {'YES' if bbc['includes_zero'] else 'NO'} |")
        w()

        w("#### Paired t-test on Monthly Return Differences")
        w()
        w("| Comparison | t-statistic | p-value | Significant (p<0.05)? |")
        w("|-|-|-|-|")

        tt = res['paired_ttest']
        w(f"| A vs B | {fmt_num(tt['a_vs_b']['t_stat'], 4)} | {fmt_num(tt['a_vs_b']['p_value'], 4)} | {'YES' if tt['a_vs_b']['p_value'] < 0.05 else 'NO'} |")
        w(f"| A vs C | {fmt_num(tt['a_vs_c']['t_stat'], 4)} | {fmt_num(tt['a_vs_c']['p_value'], 4)} | {'YES' if tt['a_vs_c']['p_value'] < 0.05 else 'NO'} |")
        w(f"| B vs C | {fmt_num(tt['b_vs_c']['t_stat'], 4)} | {fmt_num(tt['b_vs_c']['p_value'], 4)} | {'YES' if tt['b_vs_c']['p_value'] < 0.05 else 'NO'} |")
        w()

    w("## Interpretation Guide")
    w()
    w("- If B's Sharpe > A's Sharpe AND the bootstrap CI excludes zero: risk management adds")
    w("  statistically significant value.")
    w("- If B's Sharpe > A's Sharpe BUT the bootstrap CI includes zero: risk management may help")
    w("  but the evidence is not statistically significant at 95% confidence.")
    w("- If B's max drawdown is materially better than A's, risk management adds tail protection")
    w("  even if return enhancement is not significant.")
    w("- If C < B: signals subtract value net of costs in this measurement.")
    w("- If C > B: signals add value on top of risk management. The current architecture is justified.")
    w()

    w("## Conclusion")
    w()

    if us_results:
        ra = us_results['result_a']
        rb = us_results['result_b']
        rc = us_results['result_c']
        bab = us_results['bootstrap']['a_vs_b']

        sharpe_diff_ab = rb['sharpe'] - ra['sharpe']
        dd_diff_ab = rb['max_dd'] - ra['max_dd']

        w("### US Universe")
        w()

        if sharpe_diff_ab > 0.05 and not bab['includes_zero']:
            w("**VERDICT: Risk management adds STATISTICALLY SIGNIFICANT value.**")
            w(f"Sharpe improvement: {fmt_num(sharpe_diff_ab)} (B over A).")
        elif sharpe_diff_ab > 0:
            w(f"**VERDICT: Risk management shows POSITIVE but NOT STATISTICALLY SIGNIFICANT improvement.**")
            w(f"Sharpe improvement: {fmt_num(sharpe_diff_ab)} (B over A), but 95% CI includes zero.")
        else:
            w(f"**VERDICT: Risk management does NOT improve risk-adjusted returns.**")
            w(f"Sharpe difference: {fmt_num(sharpe_diff_ab)} (B minus A).")

        if abs(dd_diff_ab) > 0.01:
            dd_better = "reduced" if dd_diff_ab > 0 else "increased"
            w(f"Max drawdown {dd_better} by {fmt_pct(abs(dd_diff_ab))} (B vs A).")
        w()

        if rc:
            sharpe_diff_bc = rc['sharpe'] - rb['sharpe']
            if sharpe_diff_bc < -0.05:
                w(f"**Full engine below EW plus risk management:** Full engine Sharpe ({fmt_num(rc['sharpe'])}) < ")
                w(f"EW+risk mgmt Sharpe ({fmt_num(rb['sharpe'])}). Consider stripping signals.")
            elif sharpe_diff_bc > 0.05:
                w(f"**Signals ADD value:** Full engine Sharpe ({fmt_num(rc['sharpe'])}) > ")
                w(f"EW+risk mgmt Sharpe ({fmt_num(rb['sharpe'])}). Current architecture justified.")
            else:
                w(f"**Signals are NEUTRAL:** Full engine Sharpe ({fmt_num(rc['sharpe'])}) ~= ")
                w(f"EW+risk mgmt Sharpe ({fmt_num(rb['sharpe'])}). Signals neither help nor hurt.")
        w()

    w("## Recommendation")
    w()
    w("Based on the evidence above, the recommendation for the engine architecture is:")
    w()
    if us_results:
        ra = us_results['result_a']
        rb = us_results['result_b']
        rc = us_results['result_c']
        if rb['sharpe'] > ra['sharpe'] and rb['max_dd'] > ra['max_dd']:
            w("- **KEEP** the risk management stack, it provides measurable tail risk protection")
        elif rb['sharpe'] <= ra['sharpe']:
            w("- **INVESTIGATE FURTHER**, risk management does not clearly improve risk-adjusted returns")
            w("  on this dataset. Consider whether the complexity cost is justified by tail protection alone.")
        else:
            w("- **KEEP** the risk management stack for drawdown protection")

        if rc:
            if rc['sharpe'] < rb['sharpe'] - 0.05:
                w("- **SIGNALS SUBTRACT VALUE** in this measurement; see existential-experiment-v2.md before acting on this line")
            elif rc['sharpe'] > rb['sharpe'] + 0.05:
                w("- **KEEP SIGNALS**, they add value on top of risk management")
            else:
                w("- **SIGNALS ARE MARGINAL**, consider simplifying to 1-2 strongest signals only")
    w()

    report = "\n".join(lines)
    with open(output_path, 'w') as f:
        f.write(report)
    log(f"\nReport written to {output_path}")


def main():
    log("=" * 60)
    log("THE EXISTENTIAL EXPERIMENT")
    log("Does the risk management stack justify the engine's existence?")
    log("=" * 60)

    us_results = run_universe(
        universe_name="US (9 stocks)",
        tickers=TICKERS,
        benchmark_ticker=BENCHMARK_TICKER,
        macro_tickers=MACRO_TICKERS,
        total_capital=TOTAL_CAPITAL,
        sector_map=US_SECTOR_MAP,
        regime_weights=REGIME_WEIGHTS,
        detect_regime_fn=us_detect_regime,
        vol_target_val=VOL_TARGET_US,
        tilt_strength=TILT_STRENGTH,
        min_weight=MIN_WEIGHT,
        max_weight=MAX_WEIGHT,
        max_sector_pct=0.40,
    )

    log("\n" + "=" * 60)
    log("US RESULTS SUMMARY")
    log("=" * 60)
    for label, res in [("A (Equal Weight)", us_results['result_a']),
                       ("B (EW+RiskMgmt)", us_results['result_b'])]:
        log(f"  {label}: Sharpe={fmt_num(res['sharpe'])}, Return={fmt_pct(res['ann_return'])}, MaxDD={fmt_pct(res['max_dd'])}")
    if us_results['result_c']:
        rc = us_results['result_c']
        log(f"  C (Full Engine): Sharpe={fmt_num(rc['sharpe'])}, Return={fmt_pct(rc['ann_return'])}, MaxDD={fmt_pct(rc['max_dd'])}")
    bab = us_results['bootstrap']['a_vs_b']
    log(f"  Bootstrap Sharpe diff (B-A): [{fmt_num(bab['ci_lo'],4)}, {fmt_num(bab['ci_hi'],4)}], includes_zero={bab['includes_zero']}")

    india_results = None
    try:
        india_results = run_universe(
            universe_name="India (20 stocks)",
            tickers=INDIA_TICKERS,
            benchmark_ticker='^NSEI',
            macro_tickers=INDIA_MACRO_TICKERS,
            total_capital=INDIA_TOTAL_CAPITAL,
            sector_map=INDIA_SECTOR_MAP,
            regime_weights=INDIA_REGIME_WEIGHTS,
            detect_regime_fn=india_detect_regime,
            vol_target_val=VOL_TARGET_INDIA,
            tilt_strength=INDIA_TILT_STRENGTH,
            min_weight=INDIA_MIN_WEIGHT,
            max_weight=INDIA_MAX_WEIGHT,
            max_sector_pct=0.40,
        )

        log("\n" + "=" * 60)
        log("INDIA RESULTS SUMMARY")
        log("=" * 60)
        for label, res in [("A (Equal Weight)", india_results['result_a']),
                           ("B (EW+RiskMgmt)", india_results['result_b'])]:
            log(f"  {label}: Sharpe={fmt_num(res['sharpe'])}, Return={fmt_pct(res['ann_return'])}, MaxDD={fmt_pct(res['max_dd'])}")
        if india_results['result_c']:
            rc = india_results['result_c']
            log(f"  C (Full Engine): Sharpe={fmt_num(rc['sharpe'])}, Return={fmt_pct(rc['ann_return'])}, MaxDD={fmt_pct(rc['max_dd'])}")
    except Exception as e:
        log(f"India universe failed: {e}")
        import traceback
        traceback.print_exc(file=sys.stderr)

    output_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'existential-experiment.md')
    write_report(us_results, india_results, output_path)

    log("\nDONE.")


if __name__ == '__main__':
    main()
