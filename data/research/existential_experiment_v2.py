import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import os

import numpy as np
import pandas as pd
import yfinance as yf
from scipy.stats import ttest_rel
from datetime import datetime, timedelta
import json

from quantshield.config import (
    TICKERS, BENCHMARK_TICKER, MACRO_TICKERS, TOTAL_CAPITAL,
    REGIME_WEIGHTS, TILT_STRENGTH, MIN_WEIGHT, MAX_WEIGHT, US_SECTOR_MAP,
)
from legacy_signals import (
    VOL_SCALAR_MAX, VOL_SCALAR_MIN, VOL_TARGET_US,
    apply_sector_limits_wf, copper_gold_signal, vix_term_structure_signal, vol_target,
)
from quantshield.risk.cvar import apply_cvar_constraint
from quantshield.risk.position_limits import apply_position_limits
from quantshield.signals.regime import us_detect_regime
from quantshield.risk.hrp import hrp_weights
from quantshield.utils import log, rank_normalize
from quantshield.signals.momentum import momentum_signal, vol_adj_momentum
from quantshield.signals.mean_reversion import rsi_signal
from quantshield.signals.trend import trend_signal
from quantshield.signals.cross_asset import us_cross_asset_signals


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
    close = close.reindex(returns.index).ffill()
    volume = volume.reindex(returns.index).fillna(0)

    log(f"  Data: {len(returns)} trading days, {len(returns.columns)} stocks")
    return close, returns, volume, benchmark_returns, macro_close


def compute_cost(weight_changes, volume_data, close_data, returns_data,
                 cost_mode='sqrt', spread_bps=5.0, impact_k=0.1,
                 flat_bps=10.0, total_capital=100000):
    if cost_mode == 'zero':
        return 0.0

    if cost_mode == 'flat':
        return float(weight_changes.abs().sum() * flat_bps / 10000.0)

    total_cost = 0.0
    for ticker in weight_changes.index:
        trade_weight = abs(weight_changes.get(ticker, 0.0))
        if trade_weight < 1e-8:
            continue

        spread_cost = trade_weight * spread_bps / 10000.0
        impact_cost = 0.0
        if (ticker in volume_data.columns and ticker in close_data.columns
                and ticker in returns_data.columns):
            vol_series = volume_data[ticker].dropna()
            if len(vol_series) >= 21:
                adv_shares = float(vol_series.iloc[-21:].mean())
                avg_price = float(close_data[ticker].iloc[-1])
                adv_dollar = adv_shares * avg_price
                if adv_dollar > 0:
                    trade_value = trade_weight * total_capital
                    daily_vol = float(returns_data[ticker].iloc[-63:].std()) if len(returns_data[ticker]) >= 63 else 0.02
                    impact_cost = impact_k * np.sqrt(trade_value / adv_dollar) * daily_vol

        total_cost += spread_cost + impact_cost
    return float(total_cost)


def run_strategy_a(returns, close, volume, benchmark_returns, total_capital, cost_mode='sqrt'):
    n_stocks = len(returns.columns)
    equal_w = pd.Series(1.0 / n_stocks, index=returns.columns)

    start_idx = 252
    step_size = 21
    portfolio_values = [total_capital]
    test_dates = []
    prev_weights = None
    monthly_port_rets = []
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
            turnover_cost = compute_cost(
                weight_changes, volume.iloc[:i], close.iloc[:i], returns.iloc[:i],
                cost_mode=cost_mode, total_capital=total_capital,
            )
            turnovers.append(float(weight_changes.abs().sum()))
        prev_weights = current_weights.copy()

        port_daily = (test_returns * current_weights).sum(axis=1).values.copy()
        port_daily[0] -= turnover_cost

        for j in range(len(test_returns)):
            portfolio_values.append(portfolio_values[-1] * (1 + port_daily[j]))
            test_dates.append(test_returns.index[j])

        period_ret = (portfolio_values[-1] / portfolio_values[-len(test_returns) - 1]) - 1
        monthly_port_rets.append(period_ret)
        i += step_size

    return build_results(portfolio_values, test_dates, monthly_port_rets, turnovers, "A_EqualWeight")


def run_strategy_b(returns, close, volume, benchmark_returns, macro_close,
                   total_capital, sector_map, vol_target_val, cost_mode='sqrt'):
    n_stocks = len(returns.columns)
    start_idx = 252
    portfolio_values = [total_capital]
    test_dates = []
    prev_weights = None
    monthly_port_rets = []
    turnovers = []

    i = start_idx
    while i < len(returns):
        train_returns = returns.iloc[:i]
        train_close = close.iloc[:i]
        train_macro = macro_close.loc[macro_close.index <= train_close.index[-1]]

        try:
            regime, _, _ = us_detect_regime(train_macro)
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
            adjusted = apply_sector_limits_wf(adjusted, sector_map, 0.40)
        adjusted, _ = apply_position_limits(
            adjusted, train_returns, benchmark_returns=benchmark_returns,
            max_single_stock=0.25, max_portfolio_beta=1.5,
        )
        adjusted = apply_cvar_constraint(adjusted, train_returns, max_monthly_cvar=0.03, confidence=0.95)
        adjusted = adjusted / adjusted.sum()

        turnover_cost = 0.0
        if prev_weights is not None:
            all_tickers = adjusted.index.union(prev_weights.index)
            weight_changes = adjusted.reindex(all_tickers, fill_value=0).sub(
                prev_weights.reindex(all_tickers, fill_value=0)
            )
            turnover_cost = compute_cost(
                weight_changes, volume.iloc[:i], close.iloc[:i], returns.iloc[:i],
                cost_mode=cost_mode, total_capital=total_capital,
            )
            turnovers.append(float(weight_changes.abs().sum()))
        prev_weights = adjusted.copy()

        port_daily = (test_returns * adjusted).sum(axis=1).values.copy()
        port_daily[0] -= turnover_cost

        for j in range(len(test_returns)):
            portfolio_values.append(portfolio_values[-1] * (1 + port_daily[j]))
            test_dates.append(test_returns.index[j])

        period_ret = (portfolio_values[-1] / portfolio_values[-len(test_returns) - 1]) - 1
        monthly_port_rets.append(period_ret)
        i += step_size

    return build_results(portfolio_values, test_dates, monthly_port_rets, turnovers, "B_EW_RiskMgmt")


def run_strategy_c(returns, close, volume, benchmark_returns, macro_close,
                   total_capital, cost_mode='sqrt'):
    start_idx = 252
    step_size = 21
    portfolio_values = [total_capital]
    test_dates = []
    prev_weights = None
    monthly_port_rets = []
    turnovers = []

    i = start_idx
    while i + step_size <= len(returns):
        train_returns = returns.iloc[:i]
        train_close = close.iloc[:i]
        train_macro = macro_close.loc[macro_close.index <= train_close.index[-1]]
        train_bm = benchmark_returns.loc[benchmark_returns.index <= train_close.index[-1]]

        test_returns = returns.iloc[i:i + step_size]
        if len(test_returns) == 0:
            break

        try:
            regime, _, _ = us_detect_regime(train_macro)
            signal_weights = dict(REGIME_WEIGHTS[regime])
            signal_weights.pop('earnings', None)

            mom = rank_normalize(momentum_signal(train_close))
            rsi = rank_normalize(rsi_signal(train_close))
            vmom = rank_normalize(vol_adj_momentum(train_returns))
            trend = rank_normalize(trend_signal(train_close))

            try:
                ca_raw, _ = us_cross_asset_signals(train_close, train_macro, train_returns, benchmark_returns=train_bm)
                cross_asset = rank_normalize(ca_raw)
            except Exception:
                cross_asset = pd.Series(0.0, index=train_close.columns)

            try:
                vix_ts = rank_normalize(vix_term_structure_signal(train_close, train_macro, train_returns, regime=regime))
            except Exception:
                vix_ts = pd.Series(0.0, index=train_close.columns)

            try:
                cu_au = rank_normalize(copper_gold_signal(train_close, train_macro, train_returns))
            except Exception:
                cu_au = pd.Series(0.0, index=train_close.columns)

            composite = pd.Series(0.0, index=train_close.columns)
            for sig_name, sig_data in [
                ('momentum', mom), ('vol_adj_momentum', vmom),
                ('mean_reversion', rsi), ('trend', trend),
                ('cross_asset', cross_asset), ('vix_term_structure', vix_ts),
                ('copper_gold', cu_au),
            ]:
                if sig_name in signal_weights:
                    composite += signal_weights[sig_name] * sig_data

            composite_norm = composite.rank(pct=True)
            hrp = hrp_weights(train_returns)
            signal_tilt = composite_norm / (composite_norm.sum() + 1e-8)
            final = (1 - TILT_STRENGTH) * hrp + TILT_STRENGTH * signal_tilt
            final = (final / final.sum()).clip(lower=MIN_WEIGHT, upper=MAX_WEIGHT)
            final = final / final.sum()
            final = vol_target(train_returns, final)

            if US_SECTOR_MAP:
                final = apply_sector_limits_wf(final, US_SECTOR_MAP, 0.40)

            final, _ = apply_position_limits(
                final, train_returns, benchmark_returns=train_bm,
                max_single_stock=0.25, max_portfolio_beta=1.5,
            )
            final = apply_cvar_constraint(final, train_returns, max_monthly_cvar=0.03, confidence=0.95)
            final = final / final.sum()
        except Exception as e:
            log(f"  Strategy C fallback at step {i}: {e}")
            final = pd.Series(1.0 / len(train_close.columns), index=train_close.columns)

        turnover_cost = 0.0
        if prev_weights is not None:
            all_tickers = final.index.union(prev_weights.index)
            weight_changes = final.reindex(all_tickers, fill_value=0).sub(
                prev_weights.reindex(all_tickers, fill_value=0)
            )
            turnover_cost = compute_cost(
                weight_changes, volume.iloc[:i], close.iloc[:i], returns.iloc[:i],
                cost_mode=cost_mode, total_capital=total_capital,
            )
            turnovers.append(float(weight_changes.abs().sum()))
        prev_weights = final.copy()

        port_daily = (test_returns * final).sum(axis=1).values.copy()
        port_daily[0] -= turnover_cost

        for j in range(len(test_returns)):
            portfolio_values.append(portfolio_values[-1] * (1 + port_daily[j]))
            test_dates.append(test_returns.index[j])

        period_ret = (portfolio_values[-1] / portfolio_values[-len(test_returns) - 1]) - 1
        monthly_port_rets.append(period_ret)
        i += step_size

    return build_results(portfolio_values, test_dates, monthly_port_rets, turnovers, "C_FullEngine")


def build_results(portfolio_values, test_dates, monthly_port_rets, turnovers, name):
    pv = np.array(portfolio_values)
    daily_rets = np.diff(pv) / pv[:-1]

    ann_ret = (pv[-1] / pv[0]) ** (252.0 / max(len(daily_rets), 1)) - 1
    ann_vol = np.std(daily_rets, ddof=1) * np.sqrt(252) if len(daily_rets) > 1 else 0
    sharpe = ann_ret / (ann_vol + 1e-10)

    running_max = np.maximum.accumulate(pv)
    drawdowns = pv / running_max - 1
    max_dd = float(np.min(drawdowns))

    avg_turnover = float(np.mean(turnovers)) if turnovers else 0.0
    monthly_turnover = avg_turnover

    return {
        'name': name,
        'portfolio_values': pv,
        'dates': pd.DatetimeIndex(test_dates) if test_dates else pd.DatetimeIndex([]),
        'ann_return': float(ann_ret),
        'ann_vol': float(ann_vol),
        'sharpe': float(sharpe),
        'max_dd': float(max_dd),
        'monthly_turnover': monthly_turnover,
        'monthly_port_rets': monthly_port_rets,
        'daily_rets': daily_rets,
    }


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

    return {
        'ci_lo': round(float(np.percentile(diffs, 2.5)), 4),
        'ci_hi': round(float(np.percentile(diffs, 97.5)), 4),
        'median': round(float(np.median(diffs)), 4),
        'includes_zero': bool(np.percentile(diffs, 2.5) <= 0 <= np.percentile(diffs, 97.5)),
    }


def run_all_cost_scenarios():
    close, returns, volume, benchmark_returns, macro_close = download_data(
        TICKERS, MACRO_TICKERS, BENCHMARK_TICKER
    )

    cost_modes = ['sqrt', 'flat', 'zero']
    cost_labels = {
        'sqrt': '5bps spread + sqrt impact',
        'flat': '10bps flat',
        'zero': '0bps (theoretical)',
    }

    all_results = {}

    for mode in cost_modes:
        log(f"\n{'='*60}")
        log(f"COST MODEL: {cost_labels[mode]}")
        log(f"{'='*60}")

        result_a = run_strategy_a(returns, close, volume, benchmark_returns, TOTAL_CAPITAL, cost_mode=mode)
        result_b = run_strategy_b(returns, close, volume, benchmark_returns, macro_close,
                                  TOTAL_CAPITAL, US_SECTOR_MAP, VOL_TARGET_US, cost_mode=mode)
        result_c = run_strategy_c(returns, close, volume, benchmark_returns, macro_close,
                                  TOTAL_CAPITAL, cost_mode=mode)

        n = min(len(result_a['monthly_port_rets']), len(result_b['monthly_port_rets']),
                len(result_c['monthly_port_rets']))
        ma = result_a['monthly_port_rets'][:n]
        mb = result_b['monthly_port_rets'][:n]
        mc = result_c['monthly_port_rets'][:n]

        boot_ba = bootstrap_sharpe_diff(ma, mb)
        boot_ca = bootstrap_sharpe_diff(ma, mc)
        boot_cb = bootstrap_sharpe_diff(mb, mc)

        arr_a, arr_b, arr_c = np.array(ma), np.array(mb), np.array(mc)
        ttest_ab = ttest_rel(arr_a, arr_b) if n >= 5 else None
        ttest_ac = ttest_rel(arr_a, arr_c) if n >= 5 else None
        ttest_bc = ttest_rel(arr_b, arr_c) if n >= 5 else None

        scenario = {
            'cost_label': cost_labels[mode],
            'n_months': n,
            'A': {
                'sharpe': round(result_a['sharpe'], 4),
                'ann_return': round(result_a['ann_return'] * 100, 2),
                'ann_vol': round(result_a['ann_vol'] * 100, 2),
                'max_dd': round(result_a['max_dd'] * 100, 2),
                'monthly_turnover': round(result_a['monthly_turnover'] * 100, 2),
            },
            'B': {
                'sharpe': round(result_b['sharpe'], 4),
                'ann_return': round(result_b['ann_return'] * 100, 2),
                'ann_vol': round(result_b['ann_vol'] * 100, 2),
                'max_dd': round(result_b['max_dd'] * 100, 2),
                'monthly_turnover': round(result_b['monthly_turnover'] * 100, 2),
            },
            'C': {
                'sharpe': round(result_c['sharpe'], 4),
                'ann_return': round(result_c['ann_return'] * 100, 2),
                'ann_vol': round(result_c['ann_vol'] * 100, 2),
                'max_dd': round(result_c['max_dd'] * 100, 2),
                'monthly_turnover': round(result_c['monthly_turnover'] * 100, 2),
            },
            'bootstrap': {
                'B_minus_A': boot_ba,
                'C_minus_A': boot_ca,
                'C_minus_B': boot_cb,
            },
            'ttest': {
                'A_vs_B': {'t': round(ttest_ab.statistic, 4), 'p': round(ttest_ab.pvalue, 4)} if ttest_ab else None,
                'A_vs_C': {'t': round(ttest_ac.statistic, 4), 'p': round(ttest_ac.pvalue, 4)} if ttest_ac else None,
                'B_vs_C': {'t': round(ttest_bc.statistic, 4), 'p': round(ttest_bc.pvalue, 4)} if ttest_bc else None,
            },
        }

        all_results[mode] = scenario

        log(f"\n  Strategy A (EW):       Sharpe={scenario['A']['sharpe']}, Return={scenario['A']['ann_return']}%, Vol={scenario['A']['ann_vol']}%, MaxDD={scenario['A']['max_dd']}%")
        log(f"  Strategy B (EW+RM):    Sharpe={scenario['B']['sharpe']}, Return={scenario['B']['ann_return']}%, Vol={scenario['B']['ann_vol']}%, MaxDD={scenario['B']['max_dd']}%")
        log(f"  Strategy C (Full):     Sharpe={scenario['C']['sharpe']}, Return={scenario['C']['ann_return']}%, Vol={scenario['C']['ann_vol']}%, MaxDD={scenario['C']['max_dd']}%")
        log(f"  Bootstrap B-A: [{boot_ba['ci_lo']}, {boot_ba['ci_hi']}] median={boot_ba['median']} zero_in_CI={boot_ba['includes_zero']}")
        log(f"  Bootstrap C-A: [{boot_ca['ci_lo']}, {boot_ca['ci_hi']}] median={boot_ca['median']} zero_in_CI={boot_ca['includes_zero']}")
        log(f"  Bootstrap C-B: [{boot_cb['ci_lo']}, {boot_cb['ci_hi']}] median={boot_cb['median']} zero_in_CI={boot_cb['includes_zero']}")

    return all_results


if __name__ == '__main__':
    results = run_all_cost_scenarios()
    print(json.dumps(results, indent=2, default=str))
