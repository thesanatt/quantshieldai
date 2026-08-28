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
    REGIME_WEIGHTS, TILT_STRENGTH, MIN_WEIGHT, MAX_WEIGHT, US_SECTOR_MAP,
)
from legacy_signals import VOL_SCALAR_MAX, VOL_SCALAR_MIN, VOL_TARGET_US, compute_transaction_cost, vol_target
from quantshield.risk.cvar import apply_cvar_constraint
from quantshield.risk.position_limits import apply_position_limits
from quantshield.signals.regime import us_detect_regime
from quantshield.utils import log


def download_data(tickers, macro_tickers, benchmark, days=3650):
    end = datetime.now()
    start = end - timedelta(days=days)
    start_str = start.strftime('%Y-%m-%d')
    end_str = end.strftime('%Y-%m-%d')

    log(f"Downloading {len(tickers)} tickers from {start_str} to {end_str}")
    all_tickers = list(set(tickers + [benchmark] + macro_tickers))
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


def compute_tc(weight_changes, volume_data, close_data, returns_data, total_capital=100000):
    return compute_transaction_cost(
        weight_changes, volume_data, close_data, returns_data,
        spread_bps=5.0, impact_k=0.1, total_capital=total_capital,
    )


def build_results(portfolio_values, benchmark_values, test_dates,
                  monthly_port_rets, monthly_bm_rets, turnovers, name):
    pv = np.array(portfolio_values)
    bv = np.array(benchmark_values)
    daily_port_rets = np.diff(pv) / pv[:-1]

    ann_ret = (pv[-1] / pv[0]) ** (252.0 / max(len(daily_port_rets), 1)) - 1
    ann_vol = np.std(daily_port_rets, ddof=1) * np.sqrt(252)
    sharpe = ann_ret / (ann_vol + 1e-10)

    running_max = np.maximum.accumulate(pv)
    drawdowns = pv / running_max - 1
    max_dd = float(np.min(drawdowns))

    monthly_arr = np.array(monthly_port_rets)
    if len(monthly_arr) >= 5:
        sorted_m = np.sort(monthly_arr)
        cutoff = max(1, int(len(sorted_m) * 0.05))
        cvar_95 = float(np.mean(sorted_m[:cutoff]))
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
    recovery_days = (recovery_idx - peak_idx) if recovery_idx else (len(pv) - peak_idx)
    dd_adj_ret = ann_ret / abs(max_dd) if abs(max_dd) > 1e-10 else 0.0
    avg_turnover = float(np.mean(turnovers)) if turnovers else 0.0

    return {
        'name': name,
        'ann_return': float(ann_ret),
        'ann_vol': float(ann_vol),
        'sharpe': float(sharpe),
        'max_dd': float(max_dd),
        'cvar_95': float(cvar_95),
        'recovery_days': recovery_days,
        'dd_adj_return': float(dd_adj_ret),
        'avg_turnover': avg_turnover,
        'monthly_port_rets': list(monthly_port_rets),
        'monthly_bm_rets': list(monthly_bm_rets),
        'daily_port_rets': daily_port_rets.tolist(),
    }


def bootstrap_sharpe_diff(rets_a, rets_b, n_boot=10000):
    rets_a = np.array(rets_a)
    rets_b = np.array(rets_b)
    n = len(rets_a)
    diffs = []
    rng = np.random.default_rng(42)
    for _ in range(n_boot):
        idx = rng.integers(0, n, size=n)
        sa = np.mean(rets_a[idx]) / (np.std(rets_a[idx], ddof=1) + 1e-10) * np.sqrt(12)
        sb = np.mean(rets_b[idx]) / (np.std(rets_b[idx], ddof=1) + 1e-10) * np.sqrt(12)
        diffs.append(sa - sb)
    diffs = np.array(diffs)
    return float(np.percentile(diffs, 2.5)), float(np.percentile(diffs, 97.5)), float(np.median(diffs))


# ===== TEST 1: Equal Weight baseline (already done, re-confirm) =====

def run_equal_weight(returns, close, volume, benchmark_returns, total_capital):
    log("Test 1: Naive Equal Weight")
    n = len(returns.columns)
    eq_w = pd.Series(1.0 / n, index=returns.columns)
    start_idx = 252
    step_size = 21
    pv = [total_capital]
    bv = [total_capital]
    dates = []
    prev_w = None
    m_port, m_bm, turnov = [], [], []

    i = start_idx
    while i + step_size <= len(returns):
        test_ret = returns.iloc[i:i + step_size]
        w = eq_w.copy()
        tc = 0.0
        if prev_w is not None:
            wc = w - prev_w
            tc = compute_tc(wc, volume.iloc[:i], close.iloc[:i], returns.iloc[:i], total_capital)
            turnov.append(float(wc.abs().sum()))
        prev_w = w.copy()

        port_d = (test_ret * w).sum(axis=1).values.copy()
        port_d[0] -= tc
        bm_d = benchmark_returns.reindex(test_ret.index, fill_value=0.0).values

        for j in range(len(test_ret)):
            pv.append(pv[-1] * (1 + port_d[j]))
            bv.append(bv[-1] * (1 + bm_d[j]))
            dates.append(test_ret.index[j])

        m_port.append((pv[-1] / pv[-len(test_ret) - 1]) - 1)
        m_bm.append((bv[-1] / bv[-len(test_ret) - 1]) - 1)
        i += step_size

    return build_results(pv, bv, dates, m_port, m_bm, turnov, "EqualWeight")


# ===== TEST 2: Factor TIMING (regime-based exposure scaling) =====

def run_factor_timing(returns, close, volume, benchmark_returns, macro_close, total_capital):
    log("Test 2: Factor Timing (Regime-Based Exposure)")
    n = len(returns.columns)
    eq_w = pd.Series(1.0 / n, index=returns.columns)
    start_idx = 252
    pv = [total_capital]
    bv = [total_capital]
    dates = []
    prev_w = None
    m_port, m_bm, turnov = [], [], []

    tnx_col = '^TNX'
    has_tnx = tnx_col in macro_close.columns

    i = start_idx
    while i < len(returns):
        train_macro = macro_close.loc[macro_close.index <= returns.index[i - 1]]
        try:
            regime, _, _ = us_detect_regime(train_macro)
        except Exception:
            regime = 'risk_on'

        if regime == 'risk_on':
            equity_frac = 1.0
        elif regime == 'risk_off':
            equity_frac = 0.60
        else:
            equity_frac = 0.30

        step_size = 21
        if i + step_size > len(returns):
            step_size = len(returns) - i
        if step_size <= 0:
            break

        test_ret = returns.iloc[i:i + step_size]

        w = eq_w * equity_frac
        cash_frac = 1.0 - equity_frac

        tc = 0.0
        if prev_w is not None:
            wc = w - prev_w
            tc = compute_tc(wc, volume.iloc[:i], close.iloc[:i], returns.iloc[:i], total_capital)
            turnov.append(float(wc.abs().sum()))
        prev_w = w.copy()

        if has_tnx:
            tnx_val = train_macro[tnx_col].iloc[-1]
            daily_rf = (tnx_val / 100.0) / 252.0 if not np.isnan(tnx_val) else 0.0
        else:
            daily_rf = 0.04 / 252.0

        port_d = (test_ret * w).sum(axis=1).values.copy() + cash_frac * daily_rf
        port_d[0] -= tc
        bm_d = benchmark_returns.reindex(test_ret.index, fill_value=0.0).values

        for j in range(len(test_ret)):
            pv.append(pv[-1] * (1 + port_d[j]))
            bv.append(bv[-1] * (1 + bm_d[j]))
            dates.append(test_ret.index[j])

        m_port.append((pv[-1] / pv[-len(test_ret) - 1]) - 1)
        m_bm.append((bv[-1] / bv[-len(test_ret) - 1]) - 1)
        i += step_size

    return build_results(pv, bv, dates, m_port, m_bm, turnov, "FactorTiming")


# ===== TEST 3: Expanded Universe (Sector ETFs) =====

SECTOR_ETFS = ['XLK', 'XLV', 'XLE', 'XLF', 'XLI', 'XLC', 'XLRE', 'XLU', 'XLP', 'XLY']

def run_sector_etf_equal_weight(total_capital=100000):
    log("Test 3: Sector ETF Equal Weight")
    end = datetime.now()
    start = end - timedelta(days=3650)
    tickers = SECTOR_ETFS
    benchmark = 'SPY'
    all_t = tickers + [benchmark]
    raw = yf.download(all_t, start=start.strftime('%Y-%m-%d'), end=end.strftime('%Y-%m-%d'),
                      auto_adjust=True, progress=False)
    close = raw['Close'][tickers].dropna(how='all').ffill().dropna()
    volume = raw['Volume'][tickers].reindex(close.index).fillna(0)
    bm_close = raw['Close'][benchmark].reindex(close.index).ffill()
    returns = close.pct_change().dropna()
    bm_returns = bm_close.pct_change().reindex(returns.index).fillna(0)

    n = len(tickers)
    eq_w = pd.Series(1.0 / n, index=tickers)
    start_idx = 252
    step_size = 21
    pv = [total_capital]
    bv = [total_capital]
    dates = []
    prev_w = None
    m_port, m_bm, turnov = [], [], []

    i = start_idx
    while i + step_size <= len(returns):
        test_ret = returns.iloc[i:i + step_size]
        w = eq_w.copy()
        tc = 0.0
        if prev_w is not None:
            wc = w - prev_w
            tc = compute_transaction_cost(wc, volume.iloc[:i], close.iloc[:i], returns.iloc[:i],
                                           spread_bps=5.0, impact_k=0.1, total_capital=total_capital)
            turnov.append(float(wc.abs().sum()))
        prev_w = w.copy()
        port_d = (test_ret * w).sum(axis=1).values.copy()
        port_d[0] -= tc
        bm_d = bm_returns.reindex(test_ret.index, fill_value=0.0).values
        for j in range(len(test_ret)):
            pv.append(pv[-1] * (1 + port_d[j]))
            bv.append(bv[-1] * (1 + bm_d[j]))
            dates.append(test_ret.index[j])
        m_port.append((pv[-1] / pv[-len(test_ret) - 1]) - 1)
        m_bm.append((bv[-1] / bv[-len(test_ret) - 1]) - 1)
        i += step_size

    return build_results(pv, bv, dates, m_port, m_bm, turnov, "SectorETF_EW"), returns, close, volume, bm_returns


def run_sector_momentum(returns, close, volume, bm_returns, total_capital=100000):
    log("Test 3b: Sector Momentum Tilting")
    tickers = list(returns.columns)
    n = len(tickers)
    start_idx = 252
    step_size = 21
    pv = [total_capital]
    bv = [total_capital]
    dates = []
    prev_w = None
    m_port, m_bm, turnov = [], [], []

    i = start_idx
    while i + step_size <= len(returns):
        train_ret = returns.iloc[i - 252:i]
        test_ret = returns.iloc[i:i + step_size]

        mom_12_1 = train_ret.iloc[:-21].sum()
        mom_rank = mom_12_1.rank(pct=True)
        scores = (mom_rank - 0.5) * 2

        eq_w = pd.Series(1.0 / n, index=tickers)
        tilt = 0.5
        w = eq_w * (1 + tilt * scores)
        w = w.clip(lower=0.02)
        w = w / w.sum()

        tc = 0.0
        if prev_w is not None:
            wc = w - prev_w
            tc = compute_transaction_cost(wc, volume.iloc[:i], close.iloc[:i], returns.iloc[:i],
                                           spread_bps=5.0, impact_k=0.1, total_capital=total_capital)
            turnov.append(float(wc.abs().sum()))
        prev_w = w.copy()

        port_d = (test_ret * w).sum(axis=1).values.copy()
        port_d[0] -= tc
        bm_d = bm_returns.reindex(test_ret.index, fill_value=0.0).values
        for j in range(len(test_ret)):
            pv.append(pv[-1] * (1 + port_d[j]))
            bv.append(bv[-1] * (1 + bm_d[j]))
            dates.append(test_ret.index[j])
        m_port.append((pv[-1] / pv[-len(test_ret) - 1]) - 1)
        m_bm.append((bv[-1] / bv[-len(test_ret) - 1]) - 1)
        i += step_size

    return build_results(pv, bv, dates, m_port, m_bm, turnov, "SectorETF_Momentum")


# ===== TEST 4: Crash-Buying Protocol =====

def run_crash_buying(returns, close, volume, benchmark_returns, macro_close, total_capital):
    log("Test 4: Crash-Buying Protocol")
    n = len(returns.columns)
    eq_w = pd.Series(1.0 / n, index=returns.columns)
    start_idx = 252
    pv = [total_capital]
    bv = [total_capital]
    dates = []
    prev_w = None
    m_port, m_bm, turnov = [], [], []
    crash_buy_active = False

    vix_col = '^VIX'
    has_vix = vix_col in macro_close.columns

    tnx_col = '^TNX'
    has_tnx = tnx_col in macro_close.columns

    i = start_idx
    while i < len(returns):
        step_size = 21
        if i + step_size > len(returns):
            step_size = len(returns) - i
        if step_size <= 0:
            break

        test_ret = returns.iloc[i:i + step_size]

        if has_vix:
            current_date = returns.index[i]
            vix_data = macro_close[vix_col].loc[:current_date].dropna()
            if len(vix_data) > 0:
                vix_now = vix_data.iloc[-1]
            else:
                vix_now = 20.0
        else:
            vix_now = 20.0

        if vix_now > 30:
            equity_frac = 1.20
            crash_buy_active = True
        elif crash_buy_active and vix_now < 25:
            equity_frac = 1.00
            crash_buy_active = False
        elif crash_buy_active:
            equity_frac = 1.20
        else:
            equity_frac = 1.00

        base_cash = max(0, 1.0 - equity_frac)
        w = eq_w * equity_frac

        tc = 0.0
        if prev_w is not None:
            wc = w - prev_w
            tc = compute_tc(wc, volume.iloc[:i], close.iloc[:i], returns.iloc[:i], total_capital)
            turnov.append(float(wc.abs().sum()))
        prev_w = w.copy()

        if has_tnx:
            tnx_val = macro_close[tnx_col].loc[:returns.index[i]].dropna().iloc[-1]
            daily_rf = (tnx_val / 100.0) / 252.0 if not np.isnan(tnx_val) else 0.0
        else:
            daily_rf = 0.04 / 252.0

        leverage_cost = max(0, equity_frac - 1.0) * 0.06 / 252.0

        port_d = (test_ret * w).sum(axis=1).values.copy() + base_cash * daily_rf - leverage_cost
        port_d[0] -= tc
        bm_d = benchmark_returns.reindex(test_ret.index, fill_value=0.0).values

        for j in range(len(test_ret)):
            pv.append(pv[-1] * (1 + port_d[j]))
            bv.append(bv[-1] * (1 + bm_d[j]))
            dates.append(test_ret.index[j])

        m_port.append((pv[-1] / pv[-len(test_ret) - 1]) - 1)
        m_bm.append((bv[-1] / bv[-len(test_ret) - 1]) - 1)
        i += step_size

    return build_results(pv, bv, dates, m_port, m_bm, turnov, "CrashBuying")


# ===== TEST 4b: Crash-buying with cash buffer =====

def run_crash_buying_cash_buffer(returns, close, volume, benchmark_returns, macro_close, total_capital):
    log("Test 4b: Crash-Buying with Cash Buffer (no leverage)")
    n = len(returns.columns)
    eq_w = pd.Series(1.0 / n, index=returns.columns)
    start_idx = 252
    pv = [total_capital]
    bv = [total_capital]
    dates = []
    prev_w = None
    m_port, m_bm, turnov = [], [], []
    crash_buy_active = False

    vix_col = '^VIX'
    has_vix = vix_col in macro_close.columns
    tnx_col = '^TNX'
    has_tnx = tnx_col in macro_close.columns

    i = start_idx
    while i < len(returns):
        step_size = 21
        if i + step_size > len(returns):
            step_size = len(returns) - i
        if step_size <= 0:
            break

        test_ret = returns.iloc[i:i + step_size]

        if has_vix:
            vix_data = macro_close[vix_col].loc[:returns.index[i]].dropna()
            vix_now = vix_data.iloc[-1] if len(vix_data) > 0 else 20.0
        else:
            vix_now = 20.0

        if vix_now > 30:
            equity_frac = 1.00
            crash_buy_active = True
        elif crash_buy_active and vix_now < 25:
            equity_frac = 0.80
            crash_buy_active = False
        elif crash_buy_active:
            equity_frac = 1.00
        else:
            equity_frac = 0.80

        cash_frac = 1.0 - equity_frac
        w = eq_w * equity_frac

        tc = 0.0
        if prev_w is not None:
            wc = w - prev_w
            tc = compute_tc(wc, volume.iloc[:i], close.iloc[:i], returns.iloc[:i], total_capital)
            turnov.append(float(wc.abs().sum()))
        prev_w = w.copy()

        if has_tnx:
            tnx_val = macro_close[tnx_col].loc[:returns.index[i]].dropna().iloc[-1]
            daily_rf = (tnx_val / 100.0) / 252.0 if not np.isnan(tnx_val) else 0.0
        else:
            daily_rf = 0.04 / 252.0

        port_d = (test_ret * w).sum(axis=1).values.copy() + cash_frac * daily_rf
        port_d[0] -= tc
        bm_d = benchmark_returns.reindex(test_ret.index, fill_value=0.0).values

        for j in range(len(test_ret)):
            pv.append(pv[-1] * (1 + port_d[j]))
            bv.append(bv[-1] * (1 + bm_d[j]))
            dates.append(test_ret.index[j])

        m_port.append((pv[-1] / pv[-len(test_ret) - 1]) - 1)
        m_bm.append((bv[-1] / bv[-len(test_ret) - 1]) - 1)
        i += step_size

    return build_results(pv, bv, dates, m_port, m_bm, turnov, "CrashBuy_CashBuffer")


# ===== Regime analysis helper =====

def regime_analysis(returns, macro_close, monthly_rets, name):
    log(f"Regime analysis for {name}")
    train_start = 252
    regimes = []
    for i in range(train_start, len(returns), 21):
        train_macro = macro_close.loc[macro_close.index <= returns.index[min(i, len(returns) - 1)]]
        try:
            regime, _, _ = us_detect_regime(train_macro)
        except Exception:
            regime = 'risk_on'
        regimes.append(regime)

    n_periods = min(len(regimes), len(monthly_rets))
    regimes = regimes[:n_periods]
    rets = np.array(monthly_rets[:n_periods])

    result = {}
    for r in ['risk_on', 'risk_off', 'crisis']:
        mask = np.array([reg == r for reg in regimes])
        if mask.sum() > 0:
            r_rets = rets[mask]
            result[r] = {
                'count': int(mask.sum()),
                'mean_monthly': float(np.mean(r_rets)),
                'std_monthly': float(np.std(r_rets, ddof=1)) if mask.sum() > 1 else 0.0,
                'sharpe_monthly': float(np.mean(r_rets) / (np.std(r_rets, ddof=1) + 1e-10)) if mask.sum() > 1 else 0.0,
            }
        else:
            result[r] = {'count': 0, 'mean_monthly': 0.0, 'std_monthly': 0.0, 'sharpe_monthly': 0.0}
    return result


def main():
    log("=" * 60)
    log("SIGNAL ARCHITECTURE RETHINK ,  4 TESTS")
    log("=" * 60)

    close, returns, volume, bm_returns, macro_close = download_data(
        TICKERS, MACRO_TICKERS, BENCHMARK_TICKER, days=3650
    )

    # TEST 1: Equal Weight baseline
    ew_result = run_equal_weight(returns, close, volume, bm_returns, TOTAL_CAPITAL)

    # TEST 2: Factor Timing
    ft_result = run_factor_timing(returns, close, volume, bm_returns, macro_close, TOTAL_CAPITAL)

    # TEST 3: Sector ETFs
    sector_ew_result, sec_returns, sec_close, sec_volume, sec_bm_returns = run_sector_etf_equal_weight(TOTAL_CAPITAL)
    sector_mom_result = run_sector_momentum(sec_returns, sec_close, sec_volume, sec_bm_returns, TOTAL_CAPITAL)

    # TEST 4: Crash Buying
    cb_result = run_crash_buying(returns, close, volume, bm_returns, macro_close, TOTAL_CAPITAL)
    cb_cash_result = run_crash_buying_cash_buffer(returns, close, volume, bm_returns, macro_close, TOTAL_CAPITAL)

    # Compare all to equal weight baseline
    log("\n" + "=" * 60)
    log("RESULTS SUMMARY")
    log("=" * 60)

    all_results = {
        'EqualWeight': ew_result,
        'FactorTiming': ft_result,
        'SectorETF_EW': sector_ew_result,
        'SectorETF_Mom': sector_mom_result,
        'CrashBuying': cb_result,
        'CrashBuy_Cash': cb_cash_result,
    }

    print("\n### Performance Summary")
    print(f"{'Strategy':<20} {'Ann.Ret':>8} {'Ann.Vol':>8} {'Sharpe':>7} {'MaxDD':>8} {'CVaR95':>8} {'Recov':>6} {'DDAdj':>6} {'Turn':>6}")
    print("-" * 88)
    for name, r in all_results.items():
        print(f"{name:<20} {r['ann_return']*100:>7.2f}% {r['ann_vol']*100:>7.2f}% {r['sharpe']:>7.3f} {r['max_dd']*100:>7.2f}% {r['cvar_95']*100:>7.2f}% {r['recovery_days']:>5}d {r['dd_adj_return']:>6.3f} {r['avg_turnover']*100:>5.1f}%")

    # Bootstrap tests vs equal weight
    print("\n### Bootstrap 95% CI on Sharpe Difference vs Equal Weight (10K resamples)")
    print(f"{'Comparison':<25} {'CI Lower':>10} {'CI Upper':>10} {'Median':>10} {'Zero?':>8}")
    print("-" * 68)

    ew_monthly = ew_result['monthly_port_rets']
    for name, r in all_results.items():
        if name == 'EqualWeight':
            continue
        other_monthly = r['monthly_port_rets']
        n_common = min(len(ew_monthly), len(other_monthly))
        if n_common < 10:
            print(f"{name + ' - EW':<25} {'N/A':>10} {'N/A':>10} {'N/A':>10} {'N/A':>8}")
            continue
        ci_lo, ci_hi, med = bootstrap_sharpe_diff(other_monthly[:n_common], ew_monthly[:n_common])
        includes_zero = "YES" if ci_lo <= 0 <= ci_hi else "NO"
        print(f"{name + ' - EW':<25} {ci_lo:>10.4f} {ci_hi:>10.4f} {med:>10.4f} {includes_zero:>8}")

    # Paired t-tests
    print("\n### Paired t-test on Monthly Returns vs Equal Weight")
    print(f"{'Comparison':<25} {'t-stat':>10} {'p-value':>10} {'Sig?':>6}")
    print("-" * 55)
    for name, r in all_results.items():
        if name == 'EqualWeight':
            continue
        other_monthly = r['monthly_port_rets']
        n_common = min(len(ew_monthly), len(other_monthly))
        if n_common < 10:
            continue
        t_stat, p_val = ttest_rel(other_monthly[:n_common], ew_monthly[:n_common])
        sig = "YES" if p_val < 0.05 else "NO"
        print(f"{name + ' - EW':<25} {t_stat:>10.4f} {p_val:>10.4f} {sig:>6}")

    # Regime analysis for factor timing and crash buying
    print("\n### Regime Analysis ,  Factor Timing")
    ft_regime = regime_analysis(returns, macro_close, ft_result['monthly_port_rets'], "FactorTiming")
    ew_regime = regime_analysis(returns, macro_close, ew_result['monthly_port_rets'], "EqualWeight")
    print(f"{'Regime':<12} {'FT Mean Mo':>12} {'EW Mean Mo':>12} {'FT Sharpe':>10} {'EW Sharpe':>10} {'Periods':>8}")
    for r in ['risk_on', 'risk_off', 'crisis']:
        ft_r = ft_regime[r]
        ew_r = ew_regime[r]
        print(f"{r:<12} {ft_r['mean_monthly']*100:>11.3f}% {ew_r['mean_monthly']*100:>11.3f}% {ft_r['sharpe_monthly']:>10.3f} {ew_r['sharpe_monthly']:>10.3f} {ft_r['count']:>8}")

    print("\n### Regime Analysis ,  Crash Buying")
    cb_regime = regime_analysis(returns, macro_close, cb_result['monthly_port_rets'], "CrashBuying")
    print(f"{'Regime':<12} {'CB Mean Mo':>12} {'EW Mean Mo':>12} {'CB Sharpe':>10} {'EW Sharpe':>10} {'Periods':>8}")
    for r in ['risk_on', 'risk_off', 'crisis']:
        cb_r = cb_regime[r]
        ew_r = ew_regime[r]
        print(f"{r:<12} {cb_r['mean_monthly']*100:>11.3f}% {ew_r['mean_monthly']*100:>11.3f}% {cb_r['sharpe_monthly']:>10.3f} {ew_r['sharpe_monthly']:>10.3f} {cb_r['count']:>8}")

    # Sector momentum IC
    print("\n### Sector Momentum IC (Information Coefficient)")
    ic_values = []
    i = 252
    while i + 21 <= len(sec_returns):
        train = sec_returns.iloc[i - 252:i]
        fwd = sec_returns.iloc[i:i + 21].sum()
        mom = train.iloc[:-21].sum()
        from scipy.stats import spearmanr
        corr, p = spearmanr(mom, fwd)
        if not np.isnan(corr):
            ic_values.append(corr)
        i += 21

    ic_arr = np.array(ic_values)
    mean_ic = np.mean(ic_arr)
    ic_std = np.std(ic_arr, ddof=1)
    icir = mean_ic / (ic_std + 1e-10)
    from scipy.stats import ttest_1samp
    t_ic, p_ic = ttest_1samp(ic_arr, 0)
    print(f"  Mean IC:   {mean_ic:.4f}")
    print(f"  IC Std:    {ic_std:.4f}")
    print(f"  ICIR:      {icir:.4f}")
    print(f"  t-stat:    {t_ic:.4f}")
    print(f"  p-value:   {p_ic:.4f}")
    print(f"  N periods: {len(ic_arr)}")

    # Stock momentum IC for comparison
    print("\n### Stock Momentum IC (Individual Stocks, for comparison)")
    stock_ic_values = []
    i = 252
    while i + 21 <= len(returns):
        train = returns.iloc[i - 252:i]
        fwd = returns.iloc[i:i + 21].sum()
        mom = train.iloc[:-21].sum()
        corr, p = spearmanr(mom, fwd)
        if not np.isnan(corr):
            stock_ic_values.append(corr)
        i += 21

    sic_arr = np.array(stock_ic_values)
    mean_sic = np.mean(sic_arr)
    sic_std = np.std(sic_arr, ddof=1)
    sicir = mean_sic / (sic_std + 1e-10)
    t_sic, p_sic = ttest_1samp(sic_arr, 0)
    print(f"  Mean IC:   {mean_sic:.4f}")
    print(f"  IC Std:    {sic_std:.4f}")
    print(f"  ICIR:      {sicir:.4f}")
    print(f"  t-stat:    {t_sic:.4f}")
    print(f"  p-value:   {p_sic:.4f}")
    print(f"  N periods: {len(sic_arr)}")

    log("\nDone.")


if __name__ == '__main__':
    main()
