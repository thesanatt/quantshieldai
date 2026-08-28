import sys
import json
import warnings
import numpy as np
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta

warnings.filterwarnings('ignore')

END_DATE = datetime(2026, 4, 1)
START_DATE = END_DATE - timedelta(days=365*5 + 60)

ASSET_TICKERS = ['NIFTYBEES.NS', 'GOLDBEES.NS']
MACRO_TICKERS = ['^INDIAVIX', '^NSEI', 'USDINR=X', 'CL=F']

ALLOCATIONS = {
    'risk_on':  {'equity': 1.00, 'gold': 0.00, 'liquid': 0.00},
    'risk_off': {'equity': 0.60, 'gold': 0.30, 'liquid': 0.10},
    'crisis':   {'equity': 0.30, 'gold': 0.50, 'liquid': 0.20},
}

LIQUID_ANNUAL_RETURN = 0.06
LIQUID_DAILY_RETURN = (1 + LIQUID_ANNUAL_RETURN) ** (1/252) - 1

def download_data():
    print("Downloading asset data...", file=sys.stderr)
    all_tickers = ASSET_TICKERS + MACRO_TICKERS
    data = yf.download(all_tickers, start=START_DATE, end=END_DATE, auto_adjust=True, progress=False)
    if isinstance(data.columns, pd.MultiIndex):
        close = data['Close']
    else:
        close = data
    print(f"Columns available: {list(close.columns)}", file=sys.stderr)
    for t in all_tickers:
        if t in close.columns:
            n = close[t].dropna().shape[0]
            print(f"  {t}: {n} days", file=sys.stderr)
        else:
            print(f"  {t}: MISSING", file=sys.stderr)
    return close

def simplified_regime(vix_value):
    if pd.isna(vix_value):
        return 'risk_off'
    if vix_value > 25:
        return 'crisis'
    elif vix_value >= 18:
        return 'risk_off'
    else:
        return 'risk_on'

def full_regime(macro_close, idx):
    row = {}
    regime_scores = {'risk_on': 0, 'risk_off': 0, 'crisis': 0}

    if '^INDIAVIX' in macro_close.columns:
        vix = macro_close['^INDIAVIX'].iloc[:idx+1].dropna()
        if len(vix) > 0:
            current_vix = vix.iloc[-1]
            if current_vix < 15:
                regime_scores['risk_on'] += 3
            elif current_vix < 22:
                regime_scores['risk_off'] += 2
            else:
                regime_scores['crisis'] += 3

            if len(vix) >= 50:
                sma50 = vix.rolling(50).mean().iloc[-1]
                if current_vix > sma50 * 1.2:
                    regime_scores['crisis'] += 1
                elif current_vix > sma50:
                    regime_scores['risk_off'] += 1
                else:
                    regime_scores['risk_on'] += 1

    if '^NSEI' in macro_close.columns:
        nifty = macro_close['^NSEI'].iloc[:idx+1].dropna()
        if len(nifty) >= 50:
            sma50 = nifty.rolling(50).mean().iloc[-1]
            if nifty.iloc[-1] > sma50:
                regime_scores['risk_on'] += 1
            else:
                regime_scores['risk_off'] += 1

    if 'USDINR=X' in macro_close.columns:
        usdinr = macro_close['USDINR=X'].iloc[:idx+1].dropna()
        if len(usdinr) >= 21:
            change = (usdinr.iloc[-1] / usdinr.iloc[-21] - 1) * 100
            if change > 4:
                regime_scores['crisis'] += 1
            elif change > 2:
                regime_scores['risk_off'] += 1
            elif change < -1:
                regime_scores['risk_on'] += 1

    if 'CL=F' in macro_close.columns:
        oil = macro_close['CL=F'].iloc[:idx+1].dropna()
        if len(oil) >= 21:
            ret = (oil.iloc[-1] / oil.iloc[-21] - 1) * 100
            if ret > 10:
                regime_scores['crisis'] += 2
            elif ret > 5:
                regime_scores['risk_off'] += 1
            elif ret < -5:
                regime_scores['risk_on'] += 1

    total = sum(regime_scores.values())
    if total == 0:
        return 'risk_off'
    return max(regime_scores, key=regime_scores.get)

def compute_metrics(returns, name=""):
    returns = returns.dropna()
    if len(returns) < 50:
        return None
    total_ret = (1 + returns).prod() - 1
    ann_ret = (1 + total_ret) ** (252 / len(returns)) - 1
    ann_vol = returns.std() * np.sqrt(252)
    sharpe = ann_ret / ann_vol if ann_vol > 0 else 0

    cumulative = (1 + returns).cumprod()
    rolling_max = cumulative.cummax()
    drawdown = (cumulative - rolling_max) / rolling_max
    max_dd = drawdown.min()

    return {
        'name': name,
        'ann_return': round(ann_ret * 100, 2),
        'ann_vol': round(ann_vol * 100, 2),
        'sharpe': round(sharpe, 3),
        'max_dd': round(max_dd * 100, 2),
        'total_return': round(total_ret * 100, 2),
        'n_days': len(returns)
    }

def bootstrap_sharpe_diff(returns_a, returns_b, n_boot=10000):
    a = returns_a.values
    b = returns_b.values
    min_len = min(len(a), len(b))
    a = a[:min_len]
    b = b[:min_len]

    sharpe_a = a.mean() / a.std() * np.sqrt(252) if a.std() > 0 else 0
    sharpe_b = b.mean() / b.std() * np.sqrt(252) if b.std() > 0 else 0
    observed_diff = sharpe_a - sharpe_b

    diffs = np.zeros(n_boot)
    rng = np.random.default_rng(42)
    for i in range(n_boot):
        idx = rng.integers(0, min_len, size=min_len)
        sa = a[idx]
        sb = b[idx]
        sh_a = sa.mean() / sa.std() * np.sqrt(252) if sa.std() > 0 else 0
        sh_b = sb.mean() / sb.std() * np.sqrt(252) if sb.std() > 0 else 0
        diffs[i] = sh_a - sh_b

    ci_low = np.percentile(diffs, 2.5)
    ci_high = np.percentile(diffs, 97.5)

    return {
        'observed_diff': round(observed_diff, 4),
        'ci_95_low': round(ci_low, 4),
        'ci_95_high': round(ci_high, 4),
        'significant': ci_low > 0 or ci_high < 0
    }

def main():
    results = {}
    close = download_data()

    has_niftybees = 'NIFTYBEES.NS' in close.columns and close['NIFTYBEES.NS'].dropna().shape[0] > 252
    has_goldbees = 'GOLDBEES.NS' in close.columns and close['GOLDBEES.NS'].dropna().shape[0] > 252
    has_vix = '^INDIAVIX' in close.columns and close['^INDIAVIX'].dropna().shape[0] > 100

    results['data_availability'] = {
        'NIFTYBEES': has_niftybees,
        'GOLDBEES': has_goldbees,
        'INDIAVIX': has_vix
    }

    if not has_niftybees:
        print("NIFTYBEES.NS not available, trying ^NSEI as proxy", file=sys.stderr)
        if '^NSEI' in close.columns:
            close['NIFTYBEES.NS'] = close['^NSEI']
            has_niftybees = True

    if not has_goldbees:
        print("GOLDBEES.NS not available, trying GLD as proxy (USD gold)", file=sys.stderr)
        gld = yf.download('GLD', start=START_DATE, end=END_DATE, auto_adjust=True, progress=False)
        if not gld.empty:
            if isinstance(gld.columns, pd.MultiIndex):
                close['GOLDBEES.NS'] = gld['Close']['GLD'] if 'GLD' in gld['Close'].columns else gld['Close'].iloc[:, 0]
            else:
                close['GOLDBEES.NS'] = gld['Close']
            has_goldbees = True

    if not has_niftybees:
        print("FATAL: No equity data available", file=sys.stderr)
        print(json.dumps(results, indent=2))
        return

    close = close.ffill()

    equity_returns = close['NIFTYBEES.NS'].pct_change()
    gold_returns = close['GOLDBEES.NS'].pct_change() if has_goldbees else pd.Series(0, index=close.index)

    min_start = 252
    common_idx = close.index[min_start:]

    regime_simple = {}
    regime_full = {}
    for i in range(min_start, len(close)):
        dt = close.index[i]
        if has_vix and not pd.isna(close['^INDIAVIX'].iloc[i]):
            regime_simple[dt] = simplified_regime(close['^INDIAVIX'].iloc[i])
        else:
            regime_simple[dt] = 'risk_off'
        regime_full[dt] = full_regime(close, i)

    regime_simple_series = pd.Series(regime_simple)
    regime_full_series = pd.Series(regime_full)

    results['regime_distribution_simple'] = {
        'risk_on': int((regime_simple_series == 'risk_on').sum()),
        'risk_off': int((regime_simple_series == 'risk_off').sum()),
        'crisis': int((regime_simple_series == 'crisis').sum()),
    }
    results['regime_distribution_full'] = {
        'risk_on': int((regime_full_series == 'risk_on').sum()),
        'risk_off': int((regime_full_series == 'risk_off').sum()),
        'crisis': int((regime_full_series == 'crisis').sum()),
    }

    regime_changes_simple = (regime_simple_series != regime_simple_series.shift(1)).sum()
    regime_changes_full = (regime_full_series != regime_full_series.shift(1)).sum()
    n_days = len(regime_simple_series)

    results['regime_change_frequency'] = {
        'simple_total_changes': int(regime_changes_simple),
        'simple_avg_days_per_regime': round(n_days / regime_changes_simple, 1) if regime_changes_simple > 0 else n_days,
        'full_total_changes': int(regime_changes_full),
        'full_avg_days_per_regime': round(n_days / regime_changes_full, 1) if regime_changes_full > 0 else n_days,
    }
    print(f"Regime changes (simple): {regime_changes_simple}, avg duration: {results['regime_change_frequency']['simple_avg_days_per_regime']} days", file=sys.stderr)
    print(f"Regime changes (full): {regime_changes_full}, avg duration: {results['regime_change_frequency']['full_avg_days_per_regime']} days", file=sys.stderr)

    for regime_name, regime_series in [('simple', regime_simple_series), ('full', regime_full_series)]:
        timing_returns = []
        for dt in common_idx:
            if dt not in equity_returns.index:
                continue
            prev_dates = regime_series.index[regime_series.index < dt]
            if len(prev_dates) == 0:
                continue
            prev_regime = regime_series[prev_dates[-1]]
            alloc = ALLOCATIONS[prev_regime]

            daily_r = 0
            daily_r += alloc['equity'] * (equity_returns.get(dt, 0) if not pd.isna(equity_returns.get(dt, 0)) else 0)
            daily_r += alloc['gold'] * (gold_returns.get(dt, 0) if not pd.isna(gold_returns.get(dt, 0)) else 0)
            daily_r += alloc['liquid'] * LIQUID_DAILY_RETURN

            timing_returns.append((dt, daily_r))

        timing_series = pd.Series(dict(timing_returns))

        bh_returns = equity_returns.reindex(timing_series.index).fillna(0)

        timing_metrics = compute_metrics(timing_series, f"Regime Timing ({regime_name})")
        bh_metrics = compute_metrics(bh_returns, "Buy & Hold NIFTY")

        results[f'timing_{regime_name}'] = timing_metrics
        results[f'buyhold_{regime_name}'] = bh_metrics

        bs = bootstrap_sharpe_diff(timing_series, bh_returns)
        results[f'bootstrap_{regime_name}'] = bs

        print(f"\n== {regime_name.upper()} regime timing ==", file=sys.stderr)
        if timing_metrics:
            print(f"  Timing: Sharpe={timing_metrics['sharpe']}, Return={timing_metrics['ann_return']}%, Vol={timing_metrics['ann_vol']}%, MaxDD={timing_metrics['max_dd']}%", file=sys.stderr)
        if bh_metrics:
            print(f"  B&H:    Sharpe={bh_metrics['sharpe']}, Return={bh_metrics['ann_return']}%, Vol={bh_metrics['ann_vol']}%, MaxDD={bh_metrics['max_dd']}%", file=sys.stderr)
        print(f"  Bootstrap: diff={bs['observed_diff']}, CI=[{bs['ci_95_low']}, {bs['ci_95_high']}], sig={bs['significant']}", file=sys.stderr)

    print(f"\n== Crisis Hit Rate ==", file=sys.stderr)
    for regime_name, regime_series in [('simple', regime_simple_series), ('full', regime_full_series)]:
        crisis_dates = regime_series[regime_series == 'crisis'].index
        if len(crisis_dates) == 0:
            results[f'crisis_hit_rate_{regime_name}'] = 'No crisis detected'
            continue

        fwd_returns = []
        for dt in crisis_dates:
            future_idx = equity_returns.index[equity_returns.index > dt]
            if len(future_idx) >= 5:
                fwd_5d = equity_returns.reindex(future_idx[:5]).sum()
                fwd_returns.append(fwd_5d)

        if fwd_returns:
            fwd_arr = np.array(fwd_returns)
            results[f'crisis_hit_rate_{regime_name}'] = {
                'n_crisis_days': len(crisis_dates),
                'mean_fwd_5d_return': round(np.mean(fwd_arr) * 100, 3),
                'pct_negative_5d': round(np.mean(fwd_arr < 0) * 100, 1),
                'median_fwd_5d': round(np.median(fwd_arr) * 100, 3),
            }
            print(f"  {regime_name}: {len(crisis_dates)} crisis days, mean 5d fwd return={np.mean(fwd_arr)*100:.3f}%, {np.mean(fwd_arr<0)*100:.1f}% negative", file=sys.stderr)

    print(json.dumps({k: v for k, v in results.items() if not isinstance(v, pd.Series)}, indent=2, default=str))

if __name__ == '__main__':
    main()
