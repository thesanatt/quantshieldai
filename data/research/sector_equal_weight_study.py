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
    TICKERS, INDIA_TICKERS, US_SECTOR_MAP, INDIA_SECTOR_MAP,
)


def download_prices(tickers, days=1825):
    end = datetime.now()
    start = end - timedelta(days=days)
    raw = yf.download(tickers, start=start.strftime('%Y-%m-%d'),
                      end=end.strftime('%Y-%m-%d'), auto_adjust=True, progress=False)
    if isinstance(raw.columns, pd.MultiIndex):
        close = raw['Close']
        volume = raw['Volume']
    else:
        close = raw
        volume = raw
    close = close[tickers].ffill().dropna()
    volume = volume.reindex(close.index).fillna(0)
    returns = close.pct_change().dropna()
    close = close.loc[returns.index]
    return close, returns, volume


def get_market_caps(tickers):
    caps = {}
    for t in tickers:
        try:
            info = yf.Ticker(t).info
            caps[t] = info.get('marketCap', 0) or 0
        except Exception:
            caps[t] = 0
    return caps


def naive_equal_weight(returns, rebal_freq=21):
    n = len(returns.columns)
    w = pd.Series(1.0 / n, index=returns.columns)
    pv = [1.0]
    monthly_rets = []

    for i in range(0, len(returns), rebal_freq):
        chunk = returns.iloc[i:i + rebal_freq]
        if len(chunk) == 0:
            break
        daily = (chunk * w).sum(axis=1)
        for r in daily:
            pv.append(pv[-1] * (1 + r))
        monthly_rets.append(pv[-1] / pv[-len(chunk) - 1] - 1)

    return np.array(pv), np.array(monthly_rets)


def sector_equal_weight(returns, sector_map, rebal_freq=21):
    tickers = returns.columns.tolist()
    sectors_with_stocks = {s: [t for t in members if t in tickers]
                           for s, members in sector_map.items()
                           if any(t in tickers for t in members)}
    n_sectors = len(sectors_with_stocks)
    if n_sectors == 0:
        return naive_equal_weight(returns, rebal_freq)

    pv = [1.0]
    monthly_rets = []

    for i in range(0, len(returns), rebal_freq):
        chunk = returns.iloc[i:i + rebal_freq]
        if len(chunk) == 0:
            break

        w = pd.Series(0.0, index=tickers)
        sector_weight = 1.0 / n_sectors
        for sector, members in sectors_with_stocks.items():
            active = [m for m in members if m in tickers]
            if active:
                stock_weight = sector_weight / len(active)
                for t in active:
                    w[t] = stock_weight
        w = w / w.sum()

        daily = (chunk * w).sum(axis=1)
        for r in daily:
            pv.append(pv[-1] * (1 + r))
        monthly_rets.append(pv[-1] / pv[-len(chunk) - 1] - 1)

    return np.array(pv), np.array(monthly_rets)


def market_cap_weight(returns, market_caps, rebal_freq=21):
    tickers = returns.columns.tolist()
    caps = pd.Series({t: market_caps.get(t, 0) for t in tickers})
    total = caps.sum()
    if total == 0:
        return naive_equal_weight(returns, rebal_freq)
    w = caps / total

    pv = [1.0]
    monthly_rets = []

    for i in range(0, len(returns), rebal_freq):
        chunk = returns.iloc[i:i + rebal_freq]
        if len(chunk) == 0:
            break
        daily = (chunk * w).sum(axis=1)
        for r in daily:
            pv.append(pv[-1] * (1 + r))
        monthly_rets.append(pv[-1] / pv[-len(chunk) - 1] - 1)

    return np.array(pv), np.array(monthly_rets)


def compute_metrics(pv, monthly_rets):
    daily_rets = np.diff(pv) / pv[:-1]
    n_days = len(daily_rets)
    ann_ret = (pv[-1] / pv[0]) ** (252.0 / max(n_days, 1)) - 1
    ann_vol = np.std(daily_rets, ddof=1) * np.sqrt(252) if n_days > 1 else 0
    sharpe = ann_ret / (ann_vol + 1e-10)
    running_max = np.maximum.accumulate(pv)
    max_dd = float(np.min(pv / running_max - 1))

    return {
        'sharpe': round(sharpe, 4),
        'ann_return': round(ann_ret * 100, 2),
        'ann_vol': round(ann_vol * 100, 2),
        'max_dd': round(max_dd * 100, 2),
    }


def sector_concentration_over_time(returns, sector_map, rebal_freq=21):
    tickers = returns.columns.tolist()
    sectors_with_stocks = {s: [t for t in members if t in tickers]
                           for s, members in sector_map.items()
                           if any(t in tickers for t in members)}

    naive_concentration = []
    sector_ew_concentration = []

    n = len(tickers)
    n_sectors = len(sectors_with_stocks)

    for i in range(0, len(returns), rebal_freq):
        naive_w = pd.Series(1.0 / n, index=tickers)
        sector_totals_naive = {}
        for s, members in sectors_with_stocks.items():
            active = [m for m in members if m in tickers]
            sector_totals_naive[s] = naive_w[active].sum()
        naive_concentration.append(max(sector_totals_naive.values()) if sector_totals_naive else 0)

        sector_w = pd.Series(0.0, index=tickers)
        sector_weight = 1.0 / n_sectors
        for s, members in sectors_with_stocks.items():
            active = [m for m in members if m in tickers]
            if active:
                sw = sector_weight / len(active)
                for t in active:
                    sector_w[t] = sw
        sector_w = sector_w / sector_w.sum()
        sector_totals_sew = {}
        for s, members in sectors_with_stocks.items():
            active = [m for m in members if m in tickers]
            sector_totals_sew[s] = sector_w[active].sum()
        sector_ew_concentration.append(max(sector_totals_sew.values()) if sector_totals_sew else 0)

    return {
        'naive_max_sector': round(np.mean(naive_concentration) * 100, 2),
        'sector_ew_max_sector': round(np.mean(sector_ew_concentration) * 100, 2),
    }


def bootstrap_sharpe_diff(monthly_a, monthly_b, n_bootstrap=10000, seed=42):
    rng = np.random.default_rng(seed=seed)
    a = np.array(monthly_a)
    b = np.array(monthly_b)
    n = min(len(a), len(b))
    a, b = a[:n], b[:n]

    diffs = np.empty(n_bootstrap)
    for i in range(n_bootstrap):
        idx = rng.integers(0, n, size=n)
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


def run_universe(name, tickers, sector_map):
    print(f"\n{'='*60}", file=sys.stderr)
    print(f"UNIVERSE: {name} ({len(tickers)} stocks)", file=sys.stderr)
    print(f"{'='*60}", file=sys.stderr)

    close, returns, volume = download_prices(tickers)
    print(f"  Data: {len(returns)} days, {len(returns.columns)} stocks", file=sys.stderr)

    available_tickers = returns.columns.tolist()
    print(f"  Available: {available_tickers}", file=sys.stderr)

    print("  Fetching market caps...", file=sys.stderr)
    mcaps = get_market_caps(available_tickers)
    print(f"  Market caps: {sum(1 for v in mcaps.values() if v > 0)}/{len(mcaps)} found", file=sys.stderr)

    pv_naive, mr_naive = naive_equal_weight(returns)
    pv_sew, mr_sew = sector_equal_weight(returns, sector_map)
    pv_mcw, mr_mcw = market_cap_weight(returns, mcaps)

    metrics_naive = compute_metrics(pv_naive, mr_naive)
    metrics_sew = compute_metrics(pv_sew, mr_sew)
    metrics_mcw = compute_metrics(pv_mcw, mr_mcw)

    concentration = sector_concentration_over_time(returns, sector_map)

    n = min(len(mr_naive), len(mr_sew), len(mr_mcw))
    boot_sew_vs_naive = bootstrap_sharpe_diff(mr_naive[:n], mr_sew[:n])
    boot_mcw_vs_naive = bootstrap_sharpe_diff(mr_naive[:n], mr_mcw[:n])
    boot_sew_vs_mcw = bootstrap_sharpe_diff(mr_mcw[:n], mr_sew[:n])

    print(f"  Naive EW:     Sharpe={metrics_naive['sharpe']}, Return={metrics_naive['ann_return']}%", file=sys.stderr)
    print(f"  Sector EW:    Sharpe={metrics_sew['sharpe']}, Return={metrics_sew['ann_return']}%", file=sys.stderr)
    print(f"  Market Cap W: Sharpe={metrics_mcw['sharpe']}, Return={metrics_mcw['ann_return']}%", file=sys.stderr)
    print(f"  Concentration: Naive max sector={concentration['naive_max_sector']}%, SEW max sector={concentration['sector_ew_max_sector']}%", file=sys.stderr)

    sector_breakdown = {}
    for s, members in sector_map.items():
        active = [m for m in members if m in available_tickers]
        if active:
            n_sectors_active = sum(1 for _, ms in sector_map.items() if any(m in available_tickers for m in ms))
            naive_pct = round(len(active) / len(available_tickers) * 100, 1)
            sew_pct = round(100.0 / n_sectors_active, 1)
            sector_breakdown[s] = {
                'n_stocks': len(active),
                'naive_weight_pct': naive_pct,
                'sector_ew_weight_pct': sew_pct,
            }

    return {
        'universe': name,
        'n_stocks': len(available_tickers),
        'n_days': len(returns),
        'n_months': n,
        'naive_ew': metrics_naive,
        'sector_ew': metrics_sew,
        'market_cap_w': metrics_mcw,
        'concentration': concentration,
        'sector_breakdown': sector_breakdown,
        'bootstrap': {
            'SEW_minus_Naive': boot_sew_vs_naive,
            'MCW_minus_Naive': boot_mcw_vs_naive,
            'SEW_minus_MCW': boot_sew_vs_mcw,
        },
    }


if __name__ == '__main__':
    us_results = run_universe("US", TICKERS, US_SECTOR_MAP)
    india_results = run_universe("India", INDIA_TICKERS, INDIA_SECTOR_MAP)
    output = {'US': us_results, 'India': india_results}
    print(json.dumps(output, indent=2, default=str))
