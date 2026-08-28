import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import os

import numpy as np
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
import json
import warnings
warnings.filterwarnings('ignore')

from quantshield.config import (
    TICKERS, INDIA_TICKERS, US_SECTOR_MAP, INDIA_SECTOR_MAP,
)

np.random.seed(42)
RNG = np.random.default_rng(42)

RESULTS = {}


def log(msg):
    print(msg, file=sys.stderr)


def download_prices(tickers, start=None, end=None, days=2600):
    if end is None:
        end = datetime.now()
    if start is None:
        start = end - timedelta(days=days)
    raw = yf.download(tickers, start=start.strftime('%Y-%m-%d'),
                      end=end.strftime('%Y-%m-%d'), auto_adjust=True, progress=False)
    if isinstance(raw.columns, pd.MultiIndex):
        close = raw['Close']
    else:
        close = raw.to_frame(tickers[0]) if len(tickers) == 1 else raw
    close = close[tickers].ffill().dropna()
    returns = close.pct_change().dropna()
    close = close.loc[returns.index]
    return close, returns


def get_sector_weights(tickers, sector_map):
    sectors_with_stocks = {s: [t for t in members if t in tickers]
                           for s, members in sector_map.items()
                           if any(t in tickers for t in members)}
    n_sectors = len(sectors_with_stocks)
    if n_sectors == 0:
        return pd.Series(1.0 / len(tickers), index=tickers)
    w = pd.Series(0.0, index=tickers)
    sector_weight = 1.0 / n_sectors
    for sector, members in sectors_with_stocks.items():
        active = [m for m in members if m in tickers]
        if active:
            stock_weight = sector_weight / len(active)
            for t in active:
                w[t] = stock_weight
    return w / w.sum()


def get_naive_weights(tickers):
    return pd.Series(1.0 / len(tickers), index=tickers)


def backtest_weights(returns, weight_func, rebal_freq=21, cost_bps=0):
    cost = cost_bps / 10000.0
    pv = [1.0]
    monthly_rets = []
    drifted_w = None
    turnover_list = []

    for i in range(0, len(returns), rebal_freq):
        chunk = returns.iloc[i:i + rebal_freq]
        if len(chunk) == 0:
            break
        target_w = weight_func(returns.iloc[:i+1] if i > 0 else returns.iloc[:rebal_freq])

        if drifted_w is not None:
            turn = float(np.abs(target_w - drifted_w.reindex(target_w.index, fill_value=0)).sum())
            turnover_list.append(turn)
            cost_drag = turn * cost
            pv[-1] *= (1 - cost_drag)

        w = target_w.copy()
        start_val = pv[-1]
        holdings = w.copy()
        for j in range(len(chunk)):
            day_ret = chunk.iloc[j]
            daily_port_ret = (holdings * day_ret).sum()
            pv.append(pv[-1] * (1 + daily_port_ret))
            holdings = holdings * (1 + day_ret)
            holdings = holdings / holdings.sum()

        drifted_w = holdings.copy()
        monthly_rets.append(pv[-1] / start_val - 1)

    return np.array(pv), np.array(monthly_rets), np.array(turnover_list)


def compute_metrics(pv, monthly_rets):
    daily_rets = np.diff(pv) / pv[:-1]
    n_days = len(daily_rets)
    if n_days < 2:
        return {'sharpe': 0, 'ann_return': 0, 'ann_vol': 0, 'max_dd': 0, 'monthly_cvar': 0}
    ann_ret = (pv[-1] / pv[0]) ** (252.0 / max(n_days, 1)) - 1
    ann_vol = np.std(daily_rets, ddof=1) * np.sqrt(252)
    sharpe = ann_ret / (ann_vol + 1e-10)
    running_max = np.maximum.accumulate(pv)
    max_dd = float(np.min(pv / running_max - 1))
    if len(monthly_rets) >= 5:
        sorted_mr = np.sort(monthly_rets)
        n5 = max(1, int(len(sorted_mr) * 0.05))
        cvar = float(np.mean(sorted_mr[:n5]))
    else:
        cvar = float(np.min(monthly_rets)) if len(monthly_rets) > 0 else 0

    return {
        'sharpe': round(sharpe, 4),
        'ann_return': round(ann_ret * 100, 2),
        'ann_vol': round(ann_vol * 100, 2),
        'max_dd': round(max_dd * 100, 2),
        'monthly_cvar': round(cvar * 100, 2),
    }


def bootstrap_sharpe_diff(monthly_a, monthly_b, n_bootstrap=10000):
    a = np.array(monthly_a)
    b = np.array(monthly_b)
    n = min(len(a), len(b))
    a, b = a[:n], b[:n]
    if n < 5:
        return {'ci_lo': 0, 'ci_hi': 0, 'median': 0, 'includes_zero': True}

    diffs = np.empty(n_bootstrap)
    for i in range(n_bootstrap):
        idx = RNG.integers(0, n, size=n)
        sa, sb = a[idx], b[idx]
        sharpe_a = np.mean(sa) / (np.std(sa, ddof=1) + 1e-10) * np.sqrt(12)
        sharpe_b = np.mean(sb) / (np.std(sb, ddof=1) + 1e-10) * np.sqrt(12)
        diffs[i] = sharpe_b - sharpe_a

    return {
        'ci_lo': round(float(np.percentile(diffs, 2.5)), 4),
        'ci_hi': round(float(np.percentile(diffs, 97.5)), 4),
        'median': round(float(np.median(diffs)), 4),
        'includes_zero': bool(np.percentile(diffs, 2.5) <= 0 <= np.percentile(diffs, 97.5)),
    }


# =============================================================================
# A. WALK-FORWARD VALIDATION
# =============================================================================
def test_walk_forward(returns, sector_map):
    log("  [A] Walk-Forward Validation...")
    tickers = returns.columns.tolist()
    monthly_returns = returns.resample('ME').apply(lambda x: (1 + x).prod() - 1)

    if len(monthly_returns) < 14:
        return {'error': 'insufficient data'}

    train_window = 12
    oos_sew = []
    oos_naive = []

    for t in range(train_window, len(monthly_returns)):
        test_month = monthly_returns.iloc[t]
        w_sew = get_sector_weights(tickers, sector_map)
        w_naive = get_naive_weights(tickers)
        oos_sew.append(float((test_month * w_sew).sum()))
        oos_naive.append(float((test_month * w_naive).sum()))

    oos_sew = np.array(oos_sew)
    oos_naive = np.array(oos_naive)

    sharpe_sew = np.mean(oos_sew) / (np.std(oos_sew, ddof=1) + 1e-10) * np.sqrt(12)
    sharpe_naive = np.mean(oos_naive) / (np.std(oos_naive, ddof=1) + 1e-10) * np.sqrt(12)

    pv_sew = np.cumprod(1 + oos_sew)
    pv_naive = np.cumprod(1 + oos_naive)
    dd_sew = float(np.min(pv_sew / np.maximum.accumulate(pv_sew) - 1))
    dd_naive = float(np.min(pv_naive / np.maximum.accumulate(pv_naive) - 1))

    ann_ret_sew = (pv_sew[-1]) ** (12.0 / len(oos_sew)) - 1
    ann_ret_naive = (pv_naive[-1]) ** (12.0 / len(oos_naive)) - 1
    alpha = ann_ret_sew - ann_ret_naive

    boot = bootstrap_sharpe_diff(oos_naive, oos_sew)

    return {
        'n_oos_months': len(oos_sew),
        'sharpe_sew': round(sharpe_sew, 4),
        'sharpe_naive': round(sharpe_naive, 4),
        'sharpe_diff': round(sharpe_sew - sharpe_naive, 4),
        'ann_alpha_vs_naive': round(alpha * 100, 2),
        'max_dd_sew': round(dd_sew * 100, 2),
        'max_dd_naive': round(dd_naive * 100, 2),
        'bootstrap_95ci': boot,
    }


# =============================================================================
# B. PARAMETER SENSITIVITY
# =============================================================================
def test_parameter_sensitivity(returns, sector_map):
    log("  [B] Parameter Sensitivity...")
    tickers = returns.columns.tolist()
    results = {}

    # B1: Number of sector buckets
    log("    B1: Sector bucket counts...")
    all_stocks = [t for members in sector_map.values() for t in members if t in tickers]
    bucket_results = {}
    for n_buckets in [5, 6, 7, 8, 9, 10]:
        shuffled = all_stocks.copy()
        RNG.shuffle(shuffled)
        fake_map = {}
        for i, stock in enumerate(shuffled):
            sector_id = f"sector_{i % n_buckets}"
            if sector_id not in fake_map:
                fake_map[sector_id] = []
            fake_map[sector_id].append(stock)

        w_func = lambda r, sm=fake_map: get_sector_weights(r.columns.tolist(), sm)
        pv, mr, _ = backtest_weights(returns, w_func)
        m = compute_metrics(pv, mr)

        w_naive_func = lambda r: get_naive_weights(r.columns.tolist())
        pv_n, mr_n, _ = backtest_weights(returns, w_naive_func)
        m_n = compute_metrics(pv_n, mr_n)

        bucket_results[n_buckets] = {
            'sew_sharpe': m['sharpe'],
            'naive_sharpe': m_n['sharpe'],
            'improvement': round(m['sharpe'] - m_n['sharpe'], 4),
        }
    results['sector_buckets'] = bucket_results

    # B1b: Use actual sector map with 8 sectors (original)
    w_sew_func = lambda r: get_sector_weights(r.columns.tolist(), sector_map)
    pv_sew, mr_sew, _ = backtest_weights(returns, w_sew_func)
    m_sew_orig = compute_metrics(pv_sew, mr_sew)

    w_naive_func = lambda r: get_naive_weights(r.columns.tolist())
    pv_naive, mr_naive, _ = backtest_weights(returns, w_naive_func)
    m_naive_orig = compute_metrics(pv_naive, mr_naive)

    results['original_sew_sharpe'] = m_sew_orig['sharpe']
    results['original_naive_sharpe'] = m_naive_orig['sharpe']
    results['original_improvement'] = round(m_sew_orig['sharpe'] - m_naive_orig['sharpe'], 4)

    # B2: Universe size
    log("    B2: Universe size sensitivity...")
    universe_results = {}
    for size in [12, 15, 18, 20]:
        improvements = []
        for trial in range(50):
            if size >= len(tickers):
                sample = tickers
            else:
                sample = list(RNG.choice(tickers, size=size, replace=False))
            sub_returns = returns[sample]

            sub_sew_func = lambda r, sm=sector_map: get_sector_weights(r.columns.tolist(), sm)
            pv_s, mr_s, _ = backtest_weights(sub_returns, sub_sew_func)
            m_s = compute_metrics(pv_s, mr_s)

            sub_naive_func = lambda r: get_naive_weights(r.columns.tolist())
            pv_n, mr_n, _ = backtest_weights(sub_returns, sub_naive_func)
            m_n = compute_metrics(pv_n, mr_n)

            improvements.append(m_s['sharpe'] - m_n['sharpe'])

        universe_results[size] = {
            'mean_improvement': round(np.mean(improvements), 4),
            'median_improvement': round(np.median(improvements), 4),
            'std_improvement': round(np.std(improvements), 4),
            'pct_positive': round(np.mean(np.array(improvements) > 0) * 100, 1),
            'min': round(np.min(improvements), 4),
            'max': round(np.max(improvements), 4),
        }
    results['universe_size'] = universe_results

    # B3: Rebalance frequency
    log("    B3: Rebalance frequency...")
    rebal_results = {}
    for freq_name, freq_days in [('weekly', 5), ('biweekly', 10), ('monthly', 21), ('quarterly', 63)]:
        for cost_bps in [0, 15]:
            sew_func = lambda r, sm=sector_map: get_sector_weights(r.columns.tolist(), sm)
            pv_s, mr_s, turn_s = backtest_weights(returns, sew_func, rebal_freq=freq_days, cost_bps=cost_bps)
            m_s = compute_metrics(pv_s, mr_s)

            naive_func = lambda r: get_naive_weights(r.columns.tolist())
            pv_n, mr_n, turn_n = backtest_weights(returns, naive_func, rebal_freq=freq_days, cost_bps=cost_bps)
            m_n = compute_metrics(pv_n, mr_n)

            key = f"{freq_name}_{cost_bps}bps"
            rebal_results[key] = {
                'sew_sharpe': m_s['sharpe'],
                'naive_sharpe': m_n['sharpe'],
                'improvement': round(m_s['sharpe'] - m_n['sharpe'], 4),
                'sew_avg_turnover': round(float(np.mean(turn_s)) * 100, 2) if len(turn_s) > 0 else 0,
                'naive_avg_turnover': round(float(np.mean(turn_n)) * 100, 2) if len(turn_n) > 0 else 0,
            }
    results['rebalance_freq'] = rebal_results

    # B4: Perturb sector assignments
    log("    B4: Sector perturbation test...")
    perturbation_improvements = []
    for trial in range(100):
        perturbed_map = {}
        for s, members in sector_map.items():
            perturbed_map[s] = members.copy()

        all_assigned = [(s, t) for s, members in perturbed_map.items() for t in members if t in tickers]
        n_to_perturb = max(1, int(len(all_assigned) * 0.20))
        perturb_indices = RNG.choice(len(all_assigned), size=n_to_perturb, replace=False)
        sectors_list = list(perturbed_map.keys())

        for idx in perturb_indices:
            old_sector, stock = all_assigned[idx]
            new_sector = RNG.choice([s for s in sectors_list if s != old_sector])
            if stock in perturbed_map[old_sector]:
                perturbed_map[old_sector].remove(stock)
            perturbed_map[new_sector].append(stock)

        perturbed_map = {s: m for s, m in perturbed_map.items() if len(m) > 0}

        p_func = lambda r, sm=perturbed_map: get_sector_weights(r.columns.tolist(), sm)
        pv_p, mr_p, _ = backtest_weights(returns, p_func)
        m_p = compute_metrics(pv_p, mr_p)
        perturbation_improvements.append(m_p['sharpe'] - m_naive_orig['sharpe'])

    results['sector_perturbation'] = {
        'mean_improvement': round(np.mean(perturbation_improvements), 4),
        'median_improvement': round(np.median(perturbation_improvements), 4),
        'std': round(np.std(perturbation_improvements), 4),
        'pct_positive': round(np.mean(np.array(perturbation_improvements) > 0) * 100, 1),
        'min': round(np.min(perturbation_improvements), 4),
        'max': round(np.max(perturbation_improvements), 4),
    }

    return results


# =============================================================================
# C. TIME-PERIOD ROBUSTNESS
# =============================================================================
def test_time_periods(close, returns, sector_map):
    log("  [C] Time-Period Robustness...")
    results = {}

    periods = {
        'pre_covid_2015_2020': ('2015-01-01', '2020-01-01'),
        'post_covid_2020_2025': ('2020-01-01', '2025-12-31'),
        'includes_covid_2018_2022': ('2018-01-01', '2022-12-31'),
    }

    for name, (start, end) in periods.items():
        sub = returns.loc[start:end]
        if len(sub) < 60:
            results[name] = {'error': f'insufficient data ({len(sub)} days)'}
            continue

        sew_func = lambda r, sm=sector_map: get_sector_weights(r.columns.tolist(), sm)
        pv_s, mr_s, _ = backtest_weights(sub, sew_func)
        m_s = compute_metrics(pv_s, mr_s)

        naive_func = lambda r: get_naive_weights(r.columns.tolist())
        pv_n, mr_n, _ = backtest_weights(sub, naive_func)
        m_n = compute_metrics(pv_n, mr_n)

        boot = bootstrap_sharpe_diff(mr_n, mr_s)
        results[name] = {
            'n_days': len(sub),
            'sew': m_s,
            'naive': m_n,
            'sharpe_diff': round(m_s['sharpe'] - m_n['sharpe'], 4),
            'bootstrap': boot,
        }

    # Exclude COVID crash (Mar-Jun 2020)
    log("    Excluding COVID crash period...")
    mask = ~((returns.index >= '2020-03-01') & (returns.index <= '2020-06-30'))
    sub_excl = returns.loc[mask]
    if len(sub_excl) > 60:
        sew_func = lambda r, sm=sector_map: get_sector_weights(r.columns.tolist(), sm)
        pv_s, mr_s, _ = backtest_weights(sub_excl, sew_func)
        m_s = compute_metrics(pv_s, mr_s)

        naive_func = lambda r: get_naive_weights(r.columns.tolist())
        pv_n, mr_n, _ = backtest_weights(sub_excl, naive_func)
        m_n = compute_metrics(pv_n, mr_n)

        boot = bootstrap_sharpe_diff(mr_n, mr_s)
        results['excl_covid_crash'] = {
            'n_days': len(sub_excl),
            'sew': m_s,
            'naive': m_n,
            'sharpe_diff': round(m_s['sharpe'] - m_n['sharpe'], 4),
            'bootstrap': boot,
        }

    # Rolling 2-year windows
    log("    Rolling 2-year windows...")
    monthly_returns = returns.resample('ME').apply(lambda x: (1 + x).prod() - 1)
    window = 24
    rolling_improvements = []
    for start_idx in range(len(monthly_returns) - window + 1):
        sub_mr = monthly_returns.iloc[start_idx:start_idx + window]
        tickers = sub_mr.columns.tolist()
        w_sew = get_sector_weights(tickers, sector_map)
        w_naive = get_naive_weights(tickers)
        port_sew = (sub_mr * w_sew).sum(axis=1)
        port_naive = (sub_mr * w_naive).sum(axis=1)

        s_sew = np.mean(port_sew) / (np.std(port_sew, ddof=1) + 1e-10) * np.sqrt(12)
        s_naive = np.mean(port_naive) / (np.std(port_naive, ddof=1) + 1e-10) * np.sqrt(12)
        rolling_improvements.append(s_sew - s_naive)

    rolling_improvements = np.array(rolling_improvements)
    results['rolling_2yr'] = {
        'n_windows': len(rolling_improvements),
        'mean_improvement': round(float(np.mean(rolling_improvements)), 4),
        'median_improvement': round(float(np.median(rolling_improvements)), 4),
        'pct_positive': round(float(np.mean(rolling_improvements > 0)) * 100, 1),
        'min': round(float(np.min(rolling_improvements)), 4),
        'max': round(float(np.max(rolling_improvements)), 4),
        'std': round(float(np.std(rolling_improvements)), 4),
    }

    return results


# =============================================================================
# D. TRANSACTION COST SENSITIVITY
# =============================================================================
def test_transaction_costs(returns, sector_map):
    log("  [D] Transaction Cost Sensitivity...")
    results = {}

    cost_levels = [0, 5, 10, 15, 20, 30, 50]

    for bps in cost_levels:
        sew_func = lambda r, sm=sector_map: get_sector_weights(r.columns.tolist(), sm)
        pv_s, mr_s, turn_s = backtest_weights(returns, sew_func, cost_bps=bps)
        m_s = compute_metrics(pv_s, mr_s)

        naive_func = lambda r: get_naive_weights(r.columns.tolist())
        pv_n, mr_n, turn_n = backtest_weights(returns, naive_func, cost_bps=bps)
        m_n = compute_metrics(pv_n, mr_n)

        results[f'{bps}bps'] = {
            'sew_sharpe': m_s['sharpe'],
            'naive_sharpe': m_n['sharpe'],
            'improvement': round(m_s['sharpe'] - m_n['sharpe'], 4),
            'sew_return': m_s['ann_return'],
            'naive_return': m_n['ann_return'],
        }

    # India realistic costs
    stt_sell = 0.025  # % on sell side delivery
    brokerage = 0.03  # % each side (conservative, discount brokers ~0)
    gst_on_brokerage = brokerage * 0.18
    stamp_duty = 0.003  # % buy side
    sebi_charges = 0.0001  # negligible
    realistic_roundtrip = stt_sell + brokerage * 2 + gst_on_brokerage * 2 + stamp_duty + sebi_charges
    results['india_realistic_cost_bps'] = round(realistic_roundtrip * 100, 1)

    # Find breakeven
    improvements = [(int(k.replace('bps', '')), v['improvement']) for k, v in results.items() if 'bps' in k and k != 'india_realistic_cost_bps']
    improvements.sort()
    breakeven = None
    for i in range(len(improvements) - 1):
        c1, imp1 = improvements[i]
        c2, imp2 = improvements[i + 1]
        if imp1 > 0 and imp2 <= 0:
            breakeven = c1 + (c2 - c1) * imp1 / (imp1 - imp2)
            break
    if breakeven is None and improvements[-1][1] > 0:
        breakeven = '>50bps'
    results['breakeven_cost_bps'] = breakeven if breakeven else 'N/A (always worse)'

    return results


# =============================================================================
# E. COMPARE AGAINST ALL ALTERNATIVES
# =============================================================================
def test_alternatives(returns, sector_map, close):
    log("  [E] Alternative Strategy Comparison...")
    tickers = returns.columns.tolist()
    results = {}

    cost_bps = 15

    # 1. Naive EW
    naive_func = lambda r: get_naive_weights(r.columns.tolist())
    pv, mr, turn = backtest_weights(returns, naive_func, cost_bps=cost_bps)
    results['naive_ew'] = {**compute_metrics(pv, mr), 'avg_monthly_turnover': round(float(np.mean(turn)) * 100, 2) if len(turn) > 0 else 0}

    # 2. Sector EW
    sew_func = lambda r, sm=sector_map: get_sector_weights(r.columns.tolist(), sm)
    pv, mr, turn = backtest_weights(returns, sew_func, cost_bps=cost_bps)
    results['sector_ew'] = {**compute_metrics(pv, mr), 'avg_monthly_turnover': round(float(np.mean(turn)) * 100, 2) if len(turn) > 0 else 0}

    # 3. Market-cap weighted (use current mcap as proxy)
    log("    Fetching market caps...")
    mcaps = {}
    for t in tickers:
        try:
            info = yf.Ticker(t).info
            mcaps[t] = info.get('marketCap', 0) or 0
        except Exception:
            mcaps[t] = 0

    def mcw_func(r):
        t = r.columns.tolist()
        caps = pd.Series({tk: mcaps.get(tk, 0) for tk in t})
        total = caps.sum()
        if total == 0:
            return get_naive_weights(t)
        return caps / total

    pv, mr, turn = backtest_weights(returns, mcw_func, cost_bps=cost_bps)
    results['market_cap'] = {**compute_metrics(pv, mr), 'avg_monthly_turnover': round(float(np.mean(turn)) * 100, 2) if len(turn) > 0 else 0}

    # 4. Inverse-volatility weighted
    def inv_vol_func(r):
        t = r.columns.tolist()
        if len(r) < 63:
            return get_naive_weights(t)
        vol = r.iloc[-63:].std() * np.sqrt(252)
        inv_vol = 1.0 / (vol + 1e-10)
        return inv_vol / inv_vol.sum()

    pv, mr, turn = backtest_weights(returns, inv_vol_func, cost_bps=cost_bps)
    results['inv_vol'] = {**compute_metrics(pv, mr), 'avg_monthly_turnover': round(float(np.mean(turn)) * 100, 2) if len(turn) > 0 else 0}

    # 5. Minimum-variance (simple: use sample covariance, quarterly)
    def min_var_func(r):
        t = r.columns.tolist()
        n = len(t)
        if len(r) < 63:
            return get_naive_weights(t)
        cov = r.iloc[-63:].cov().values * 252
        try:
            inv_cov = np.linalg.inv(cov + np.eye(n) * 1e-6)
            ones = np.ones(n)
            w = inv_cov @ ones / (ones @ inv_cov @ ones)
            w = np.maximum(w, 0)
            if w.sum() > 0:
                w = w / w.sum()
            else:
                w = np.ones(n) / n
            return pd.Series(w, index=t)
        except Exception:
            return get_naive_weights(t)

    pv, mr, turn = backtest_weights(returns, min_var_func, rebal_freq=63, cost_bps=cost_bps)
    results['min_var'] = {**compute_metrics(pv, mr), 'avg_monthly_turnover': round(float(np.mean(turn)) * 100, 2) if len(turn) > 0 else 0}

    return results


# =============================================================================
# F. TURNOVER AND EXECUTION ANALYSIS
# =============================================================================
def test_turnover(returns, sector_map):
    log("  [F] Turnover Analysis...")
    tickers = returns.columns.tolist()

    sew_func = lambda r, sm=sector_map: get_sector_weights(r.columns.tolist(), sm)
    _, _, turn_s = backtest_weights(returns, sew_func)
    naive_func = lambda r: get_naive_weights(r.columns.tolist())
    _, _, turn_n = backtest_weights(returns, naive_func)

    avg_turn_sew = float(np.mean(turn_s)) if len(turn_s) > 0 else 0
    avg_turn_naive = float(np.mean(turn_n)) if len(turn_n) > 0 else 0

    # Compute excess return
    pv_s, mr_s, _ = backtest_weights(returns, sew_func)
    m_s = compute_metrics(pv_s, mr_s)
    pv_n, mr_n, _ = backtest_weights(returns, naive_func)
    m_n = compute_metrics(pv_n, mr_n)

    excess_return = (m_s['ann_return'] - m_n['ann_return']) / 100.0
    excess_turnover_annual = (avg_turn_sew - avg_turn_naive) * 12
    if abs(excess_turnover_annual) > 1e-6:
        breakeven_cost_pct = excess_return / excess_turnover_annual
        breakeven_cost_bps = breakeven_cost_pct * 10000
    else:
        breakeven_cost_bps = float('inf')

    n_trades_sew = len(tickers)
    n_trades_naive = len(tickers)

    return {
        'avg_monthly_turnover_sew': round(avg_turn_sew * 100, 2),
        'avg_monthly_turnover_naive': round(avg_turn_naive * 100, 2),
        'excess_annual_turnover': round(excess_turnover_annual * 100, 2),
        'excess_annual_return_pct': round(excess_return * 100, 2),
        'breakeven_cost_bps': round(breakeven_cost_bps, 1) if breakeven_cost_bps != float('inf') else 'inf',
        'avg_trades_per_rebalance_sew': n_trades_sew,
        'avg_trades_per_rebalance_naive': n_trades_naive,
    }


# =============================================================================
# G. SURVIVORSHIP BIAS ASSESSMENT
# =============================================================================
def test_survivorship(returns, sector_map, tickers):
    log("  [G] Survivorship Bias Assessment...")

    dropped_stocks = [
        'YESBANK.NS', 'ZEEL.NS', 'VEDL.NS', 'GAIL.NS', 'INFRATEL.NS',
        'IBULHSGFIN.NS', 'UPL.NS'
    ]
    log(f"    Stocks dropped from Nifty50 since 2019: {dropped_stocks}")

    available_replacements = []
    for t in dropped_stocks:
        try:
            data = yf.download(t, start='2019-01-01', end='2020-01-01', progress=False)
            if len(data) > 100:
                available_replacements.append(t)
        except Exception:
            pass
    log(f"    Available replacement stocks with data: {available_replacements}")

    mid_cap_alternatives = ['JUBLFOOD.NS', 'MUTHOOTFIN.NS', 'BANDHANBNK.NS',
                            'PETRONET.NS', 'NMDC.NS', 'BIOCON.NS']
    for t in mid_cap_alternatives:
        try:
            data = yf.download(t, start='2019-01-01', end='2020-01-01', progress=False)
            if len(data) > 100 and t not in available_replacements:
                available_replacements.append(t)
        except Exception:
            pass
    log(f"    Total replacement pool: {available_replacements}")

    trial_results = []
    n_trials = min(20, max(5, len(available_replacements) * 3))

    for trial in range(n_trials):
        modified_tickers = tickers.copy()
        n_replace = min(3, len(available_replacements))
        if n_replace == 0:
            break
        replacements = list(RNG.choice(available_replacements, size=n_replace, replace=False))
        stocks_to_drop = list(RNG.choice(tickers, size=n_replace, replace=False))

        for old, new in zip(stocks_to_drop, replacements):
            idx = modified_tickers.index(old)
            modified_tickers[idx] = new

        try:
            _, mod_returns = download_prices(modified_tickers)
            available = mod_returns.columns.tolist()

            modified_sector_map = {}
            for s, members in sector_map.items():
                new_members = []
                for m in members:
                    if m in available:
                        new_members.append(m)
                if new_members:
                    modified_sector_map[s] = new_members
            for rep in replacements:
                if rep in available:
                    placed = False
                    for s in modified_sector_map:
                        if not placed:
                            modified_sector_map[s].append(rep)
                            placed = True

            sew_func = lambda r, sm=modified_sector_map: get_sector_weights(r.columns.tolist(), sm)
            pv_s, mr_s, _ = backtest_weights(mod_returns, sew_func)
            m_s = compute_metrics(pv_s, mr_s)

            naive_func = lambda r: get_naive_weights(r.columns.tolist())
            pv_n, mr_n, _ = backtest_weights(mod_returns, naive_func)
            m_n = compute_metrics(pv_n, mr_n)

            trial_results.append({
                'replaced': list(zip(stocks_to_drop, replacements)),
                'sew_sharpe': m_s['sharpe'],
                'naive_sharpe': m_n['sharpe'],
                'improvement': round(m_s['sharpe'] - m_n['sharpe'], 4),
            })
        except Exception as e:
            log(f"    Trial {trial} failed: {e}")
            continue

    improvements = [t['improvement'] for t in trial_results]

    return {
        'dropped_nifty50_stocks': dropped_stocks,
        'available_replacements': available_replacements,
        'n_trials': len(trial_results),
        'mean_improvement': round(np.mean(improvements), 4) if improvements else 0,
        'median_improvement': round(np.median(improvements), 4) if improvements else 0,
        'pct_positive': round(np.mean(np.array(improvements) > 0) * 100, 1) if improvements else 0,
        'min': round(np.min(improvements), 4) if improvements else 0,
        'max': round(np.max(improvements), 4) if improvements else 0,
        'hypothesis_test': 'DIFFERENCE likely unaffected by survivorship' if (improvements and np.mean(np.array(improvements) > 0) > 50) else 'SURVIVORSHIP MAY AFFECT DIFFERENCE',
    }


# =============================================================================
# H. US OUT-OF-SAMPLE
# =============================================================================
def test_us_oos():
    log("  [H] US Out-of-Sample Test...")
    us_tickers = TICKERS
    us_sector_map = US_SECTOR_MAP

    close, returns = download_prices(us_tickers)
    tickers = returns.columns.tolist()
    log(f"    US data: {len(returns)} days, {len(tickers)} stocks")

    sew_func = lambda r, sm=us_sector_map: get_sector_weights(r.columns.tolist(), sm)
    pv_s, mr_s, turn_s = backtest_weights(returns, sew_func, cost_bps=15)
    m_s = compute_metrics(pv_s, mr_s)

    naive_func = lambda r: get_naive_weights(r.columns.tolist())
    pv_n, mr_n, turn_n = backtest_weights(returns, naive_func, cost_bps=15)
    m_n = compute_metrics(pv_n, mr_n)

    boot = bootstrap_sharpe_diff(mr_n, mr_s)

    return {
        'n_stocks': len(tickers),
        'n_days': len(returns),
        'n_sectors': len([s for s, m in us_sector_map.items() if any(t in tickers for t in m)]),
        'sew': m_s,
        'naive': m_n,
        'sharpe_diff': round(m_s['sharpe'] - m_n['sharpe'], 4),
        'bootstrap': boot,
        'sector_breakdown': {s: [t for t in m if t in tickers] for s, m in us_sector_map.items()},
    }


# =============================================================================
# MAIN
# =============================================================================
if __name__ == '__main__':
    log("=" * 70)
    log("SECTOR-EW DEEP VALIDATION")
    log("=" * 70)

    log("\nDownloading India data...")
    india_close, india_returns = download_prices(INDIA_TICKERS)
    india_tickers = india_returns.columns.tolist()
    log(f"India: {len(india_returns)} days, {len(india_tickers)} stocks")
    log(f"Date range: {india_returns.index[0].date()} to {india_returns.index[-1].date()}")

    log("\n[A] Walk-Forward Validation")
    RESULTS['A_walk_forward'] = test_walk_forward(india_returns, INDIA_SECTOR_MAP)
    log(f"  Result: {json.dumps(RESULTS['A_walk_forward'], indent=2, default=str)}")

    log("\n[B] Parameter Sensitivity")
    RESULTS['B_parameter_sensitivity'] = test_parameter_sensitivity(india_returns, INDIA_SECTOR_MAP)

    log("\n[C] Time-Period Robustness")
    RESULTS['C_time_periods'] = test_time_periods(india_close, india_returns, INDIA_SECTOR_MAP)

    log("\n[D] Transaction Cost Sensitivity")
    RESULTS['D_transaction_costs'] = test_transaction_costs(india_returns, INDIA_SECTOR_MAP)

    log("\n[E] Alternative Strategies")
    RESULTS['E_alternatives'] = test_alternatives(india_returns, INDIA_SECTOR_MAP, india_close)

    log("\n[F] Turnover Analysis")
    RESULTS['F_turnover'] = test_turnover(india_returns, INDIA_SECTOR_MAP)

    log("\n[G] Survivorship Bias")
    RESULTS['G_survivorship'] = test_survivorship(india_returns, INDIA_SECTOR_MAP, INDIA_TICKERS)

    log("\n[H] US Out-of-Sample")
    RESULTS['H_us_oos'] = test_us_oos()

    log("\n" + "=" * 70)
    log("ALL TESTS COMPLETE")
    log("=" * 70)

    print(json.dumps(RESULTS, indent=2, default=str))
