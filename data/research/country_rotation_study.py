import sys
import json
import warnings
import numpy as np
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta

warnings.filterwarnings('ignore')

END_DATE = datetime(2026, 4, 1)
START_DATE = END_DATE - timedelta(days=365*7 + 60)

COUNTRY_ETFS = {
    'India': '^NSEI',
    'US': 'SPY',
    'China': 'FXI',
    'Brazil': 'EWZ',
    'Indonesia': 'EIDO',
    'Japan': 'EWJ',
}

APPROX_MCAP_WEIGHTS = {
    'India': 0.04,
    'US': 0.60,
    'China': 0.10,
    'Brazil': 0.02,
    'Indonesia': 0.01,
    'Japan': 0.06,
}

def download_data():
    print("Downloading country ETF data...", file=sys.stderr)
    tickers = list(COUNTRY_ETFS.values())
    data = yf.download(tickers, start=START_DATE, end=END_DATE, auto_adjust=True, progress=False)
    if isinstance(data.columns, pd.MultiIndex):
        close = data['Close']
    else:
        close = data

    country_close = pd.DataFrame()
    for country, ticker in COUNTRY_ETFS.items():
        if ticker in close.columns and close[ticker].dropna().shape[0] > 252:
            country_close[country] = close[ticker]
            print(f"  {country} ({ticker}): {close[ticker].dropna().shape[0]} days", file=sys.stderr)
        else:
            print(f"  {country} ({ticker}): MISSING or insufficient data", file=sys.stderr)

    country_close = country_close.ffill().dropna(how='any')
    return country_close

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

def country_momentum_strategy(close, lookback_months=12, rebal_months=3, top_n=2, cost_bps=0):
    daily_returns = close.pct_change()
    n_countries = close.shape[1]
    lookback_days = lookback_months * 21

    rebal_dates = []
    months_seen = set()
    month_count = 0
    for dt in close.index:
        key = (dt.year, dt.month)
        if key not in months_seen:
            months_seen.add(key)
            month_count += 1
            if month_count % rebal_months == 0:
                rebal_dates.append(dt)

    portfolio_returns = []
    turnovers = []
    prev_weights = {}

    for i, rdate in enumerate(rebal_dates):
        loc = close.index.get_loc(rdate)
        if loc < lookback_days + 21:
            continue

        mom = close.iloc[loc] / close.iloc[loc - lookback_days] - 1

        ranked = mom.sort_values(ascending=False)
        weights = {}
        top_countries = ranked.index[:top_n].tolist()
        bottom_countries = [c for c in ranked.index if c not in top_countries]

        weight_top = 0.40
        weight_rest = (1 - weight_top * top_n) / max(len(bottom_countries), 1)
        for c in top_countries:
            weights[c] = weight_top
        for c in bottom_countries:
            weights[c] = weight_rest

        if i + 1 < len(rebal_dates):
            next_rdate = rebal_dates[i + 1]
        else:
            next_rdate = close.index[-1]

        mask = (daily_returns.index > rdate) & (daily_returns.index <= next_rdate)
        period_returns = daily_returns.loc[mask]

        if period_returns.empty:
            continue

        weighted_daily = sum(weights.get(c, 0) * period_returns[c] for c in close.columns)

        if prev_weights:
            turnover = sum(abs(weights.get(c, 0) - prev_weights.get(c, 0)) for c in close.columns) / 2
        else:
            turnover = 1.0
        turnovers.append(turnover)

        cost = turnover * cost_bps / 10000
        weighted_daily.iloc[0] -= cost

        portfolio_returns.append(weighted_daily)
        prev_weights = weights

    if not portfolio_returns:
        return None, 0
    combined = pd.concat(portfolio_returns)
    combined = combined[~combined.index.duplicated(keep='first')]
    return combined, np.mean(turnovers) if turnovers else 0

def equal_weight_strategy(close, rebal_months=3, cost_bps=0):
    daily_returns = close.pct_change()
    n = close.shape[1]
    ew_daily = daily_returns.mean(axis=1)
    return ew_daily

def mcap_weight_strategy(close, cost_bps=0):
    daily_returns = close.pct_change()
    countries = close.columns
    total_w = sum(APPROX_MCAP_WEIGHTS.get(c, 0.01) for c in countries)
    weights = {c: APPROX_MCAP_WEIGHTS.get(c, 0.01) / total_w for c in countries}

    weighted_daily = sum(weights[c] * daily_returns[c] for c in countries)
    return weighted_daily

def walk_forward_country_momentum(close, lookback_months=12, rebal_months=3, top_n=2, cost_bps=0, train_months=12):
    daily_returns = close.pct_change()
    lookback_days = lookback_months * 21
    n_countries = close.shape[1]

    rebal_dates = []
    months_seen = set()
    month_count = 0
    for dt in close.index:
        key = (dt.year, dt.month)
        if key not in months_seen:
            months_seen.add(key)
            month_count += 1
            if month_count % rebal_months == 0:
                rebal_dates.append(dt)

    min_start = lookback_days + train_months * 21

    oos_returns = []
    for i, rdate in enumerate(rebal_dates):
        loc = close.index.get_loc(rdate)
        if loc < min_start:
            continue

        mom = close.iloc[loc] / close.iloc[loc - lookback_days] - 1
        ranked = mom.sort_values(ascending=False)
        top_countries = ranked.index[:top_n].tolist()
        bottom_countries = [c for c in ranked.index if c not in top_countries]

        weights = {}
        weight_top = 0.40
        weight_rest = (1 - weight_top * top_n) / max(len(bottom_countries), 1)
        for c in top_countries:
            weights[c] = weight_top
        for c in bottom_countries:
            weights[c] = weight_rest

        if i + 1 < len(rebal_dates):
            next_rdate = rebal_dates[i + 1]
        else:
            next_rdate = close.index[-1]

        mask = (daily_returns.index > rdate) & (daily_returns.index <= next_rdate)
        period_returns = daily_returns.loc[mask]

        if period_returns.empty:
            continue

        weighted_daily = sum(weights.get(c, 0) * period_returns[c] for c in close.columns)
        cost = sum(abs(weights.get(c, 0) - 1/n_countries) for c in close.columns) / 2 * cost_bps / 10000
        weighted_daily.iloc[0] -= cost

        oos_returns.append(weighted_daily)

    if not oos_returns:
        return None
    combined = pd.concat(oos_returns)
    return combined

def main():
    results = {}

    close = download_data()
    results['countries_available'] = list(close.columns)
    results['n_countries'] = len(close.columns)
    results['date_range'] = f"{close.index[0].strftime('%Y-%m-%d')} to {close.index[-1].strftime('%Y-%m-%d')}"
    results['n_trading_days'] = len(close)

    print(f"\n{'='*80}", file=sys.stderr)
    print(f"COUNTRY ROTATION STUDY", file=sys.stderr)
    print(f"Universe: {list(close.columns)}, {results['date_range']}", file=sys.stderr)
    print(f"{'='*80}\n", file=sys.stderr)

    daily_returns = close.pct_change()
    per_country = {}
    for c in close.columns:
        m = compute_metrics(daily_returns[c], c)
        if m:
            per_country[c] = m
    results['per_country_metrics'] = per_country
    for c, m in per_country.items():
        print(f"  {c}: Sharpe={m['sharpe']}, Return={m['ann_return']}%, Vol={m['ann_vol']}%", file=sys.stderr)

    print(f"\n== Strategy A: Momentum Top-2 Overweight ==", file=sys.stderr)
    strat_a_results = {}
    for cost in [0, 5, 10]:
        ret, turnover = country_momentum_strategy(close, lookback_months=12, rebal_months=3, top_n=2, cost_bps=cost)
        if ret is not None:
            m = compute_metrics(ret, f"Mom Top-2 ({cost}bps)")
            if m:
                m['avg_turnover'] = round(turnover * 100, 1)
                strat_a_results[f'cost_{cost}bps'] = m
                if cost == 0:
                    strat_a_results['returns'] = ret
                print(f"  {cost}bps: Sharpe={m['sharpe']}, Return={m['ann_return']}%, Turnover={m['avg_turnover']}%", file=sys.stderr)
    results['strategy_a'] = {k: v for k, v in strat_a_results.items() if not isinstance(v, pd.Series)}

    print(f"\n== Strategy B: Equal Weight ==", file=sys.stderr)
    ew_ret = equal_weight_strategy(close)
    ew_metrics = compute_metrics(ew_ret, "Equal Weight")
    results['strategy_b'] = ew_metrics
    if ew_metrics:
        print(f"  EW: Sharpe={ew_metrics['sharpe']}, Return={ew_metrics['ann_return']}%, Vol={ew_metrics['ann_vol']}%", file=sys.stderr)

    print(f"\n== Strategy C: Market-Cap Weight ==", file=sys.stderr)
    mcap_ret = mcap_weight_strategy(close)
    mcap_metrics = compute_metrics(mcap_ret, "Market-Cap Weight")
    results['strategy_c'] = mcap_metrics
    if mcap_metrics:
        print(f"  MCap: Sharpe={mcap_metrics['sharpe']}, Return={mcap_metrics['ann_return']}%, Vol={mcap_metrics['ann_vol']}%", file=sys.stderr)

    print(f"\n== Walk-Forward OOS ==", file=sys.stderr)
    wf_results = {}
    for cost in [0, 5, 10]:
        wf_ret = walk_forward_country_momentum(close, lookback_months=12, rebal_months=3, top_n=2, cost_bps=cost)
        if wf_ret is not None:
            wf_m = compute_metrics(wf_ret, f"WF Mom ({cost}bps)")
            wf_results[f'cost_{cost}bps'] = wf_m
            if cost == 0:
                wf_results['returns'] = wf_ret
            if wf_m:
                print(f"  WF {cost}bps: Sharpe={wf_m['sharpe']}, Return={wf_m['ann_return']}%", file=sys.stderr)
    results['walk_forward'] = {k: v for k, v in wf_results.items() if not isinstance(v, pd.Series)}

    print(f"\n== Bootstrap 95% CI ==", file=sys.stderr)
    bootstrap_results = {}

    if 'returns' in strat_a_results and ew_ret is not None:
        bs_a = bootstrap_sharpe_diff(strat_a_results['returns'], ew_ret)
        bootstrap_results['mom_vs_ew'] = bs_a
        print(f"  Mom vs EW: diff={bs_a['observed_diff']}, CI=[{bs_a['ci_95_low']}, {bs_a['ci_95_high']}], sig={bs_a['significant']}", file=sys.stderr)

    if 'returns' in wf_results and ew_ret is not None:
        bs_wf = bootstrap_sharpe_diff(wf_results['returns'], ew_ret)
        bootstrap_results['wf_mom_vs_ew'] = bs_wf
        print(f"  WF Mom vs EW: diff={bs_wf['observed_diff']}, CI=[{bs_wf['ci_95_low']}, {bs_wf['ci_95_high']}], sig={bs_wf['significant']}", file=sys.stderr)

    if mcap_ret is not None and ew_ret is not None:
        bs_mcap = bootstrap_sharpe_diff(mcap_ret, ew_ret)
        bootstrap_results['mcap_vs_ew'] = bs_mcap
        print(f"  MCap vs EW: diff={bs_mcap['observed_diff']}, CI=[{bs_mcap['ci_95_low']}, {bs_mcap['ci_95_high']}], sig={bs_mcap['significant']}", file=sys.stderr)

    results['bootstrap'] = bootstrap_results

    corr = daily_returns.corr()
    results['correlation_matrix'] = {c: {c2: round(corr.loc[c, c2], 3) for c2 in corr.columns} for c in corr.index}
    print(f"\n== Correlation Matrix ==", file=sys.stderr)
    print(corr.round(3).to_string(), file=sys.stderr)

    print(json.dumps({k: v for k, v in results.items() if not isinstance(v, pd.Series)}, indent=2, default=str))

if __name__ == '__main__':
    main()
