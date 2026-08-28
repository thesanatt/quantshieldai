import sys
import json
import warnings
import numpy as np
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta

warnings.filterwarnings('ignore')

MIDCAP_TICKERS = [
    'POLYCAB.NS', 'TRENT.NS', 'PERSISTENT.NS', 'COFORGE.NS', 'MPHASIS.NS',
    'ASTRAL.NS', 'PIIND.NS', 'VOLTAS.NS', 'CUMMINSIND.NS', 'TATACOMM.NS',
    'CROMPTON.NS', 'KPITTECH.NS', 'DEEPAKNTR.NS', 'AUROPHARMA.NS', 'JUBLFOOD.NS',
    'OBEROIRLTY.NS', 'GODREJCP.NS', 'MUTHOOTFIN.NS', 'FEDERALBNK.NS', 'IDFCFIRSTB.NS',
    'DIXON.NS', 'LINDEINDIA.NS', 'PAGEIND.NS', 'ATUL.NS', 'ESCORTS.NS',
    'TATAELXSI.NS', 'SAIL.NS', 'NMDC.NS', 'PEL.NS', 'LTTS.NS'
]

END_DATE = datetime(2026, 4, 1)
START_DATE = END_DATE - timedelta(days=365*5 + 60)

def download_data():
    print("Downloading midcap data...", file=sys.stderr)
    data = yf.download(MIDCAP_TICKERS, start=START_DATE, end=END_DATE, auto_adjust=True, progress=False)
    if isinstance(data.columns, pd.MultiIndex):
        close = data['Close']
    else:
        close = data
    valid_tickers = [t for t in MIDCAP_TICKERS if t in close.columns and close[t].dropna().shape[0] > 252]
    close = close[valid_tickers].dropna(how='all')
    close = close.ffill().dropna(how='any')
    print(f"Valid tickers: {len(valid_tickers)} / {len(MIDCAP_TICKERS)}", file=sys.stderr)
    return close, valid_tickers

def compute_momentum(close, lookback_months, skip_months=1):
    lookback_days = lookback_months * 21
    skip_days = skip_months * 21
    if len(close) < lookback_days + skip_days:
        return pd.DataFrame()

    past = close.shift(skip_days)
    far_past = close.shift(lookback_days + skip_days)
    momentum = past / far_past - 1
    return momentum

def run_momentum_strategy(close, lookback_months, skip_months=1, tercile_size=None, cost_bps=0):
    n_stocks = close.shape[1]
    if tercile_size is None:
        tercile_size = max(n_stocks // 3, 1)

    daily_returns = close.pct_change()

    rebal_dates = []
    months_seen = set()
    for dt in close.index:
        key = (dt.year, dt.month)
        if key not in months_seen:
            months_seen.add(key)
            rebal_dates.append(dt)

    lookback_days = lookback_months * 21
    skip_days = skip_months * 21
    min_history = lookback_days + skip_days + 10

    portfolio_returns = []
    turnovers = []
    prev_holdings = set()

    for i, rdate in enumerate(rebal_dates):
        loc = close.index.get_loc(rdate)
        if loc < min_history:
            continue

        window = close.iloc[:loc+1]
        mom = compute_momentum(window, lookback_months, skip_months)
        if mom.empty or mom.iloc[-1].isna().all():
            continue

        scores = mom.iloc[-1].dropna()
        if len(scores) < tercile_size:
            continue

        top_stocks = scores.nlargest(tercile_size).index.tolist()

        if i + 1 < len(rebal_dates):
            next_rdate = rebal_dates[i + 1]
        else:
            next_rdate = close.index[-1]

        mask = (daily_returns.index > rdate) & (daily_returns.index <= next_rdate)
        period_returns = daily_returns.loc[mask, top_stocks]

        if period_returns.empty:
            continue

        ew_daily = period_returns.mean(axis=1)

        current_holdings = set(top_stocks)
        if prev_holdings:
            turnover = len(current_holdings.symmetric_difference(prev_holdings)) / (2 * tercile_size)
        else:
            turnover = 1.0
        turnovers.append(turnover)

        cost = turnover * cost_bps / 10000
        ew_daily.iloc[0] -= cost

        portfolio_returns.append(ew_daily)
        prev_holdings = current_holdings

    if not portfolio_returns:
        return None

    combined = pd.concat(portfolio_returns)
    combined = combined[~combined.index.duplicated(keep='first')]
    return combined, np.mean(turnovers) if turnovers else 0

def run_equal_weight(close, cost_bps=0):
    daily_returns = close.pct_change().dropna(how='all')
    ew_daily = daily_returns.mean(axis=1)
    return ew_daily

def compute_metrics(returns, name=""):
    if returns is None or len(returns) < 50:
        return None
    returns = returns.dropna()
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

def walk_forward_oos(close, lookback_months, train_months=12, test_months=1, cost_bps=0):
    daily_returns = close.pct_change()
    n_stocks = close.shape[1]
    tercile_size = max(n_stocks // 3, 1)

    lookback_days = lookback_months * 21
    skip_days = 21
    min_days = lookback_days + skip_days + train_months * 21

    oos_returns = []

    all_dates = close.index
    start_idx = min_days

    test_days = test_months * 21

    idx = start_idx
    while idx < len(all_dates) - test_days:
        rdate = all_dates[idx]
        window = close.iloc[:idx+1]
        mom = compute_momentum(window, lookback_months, 1)
        if mom.empty:
            idx += test_days
            continue

        scores = mom.iloc[-1].dropna()
        if len(scores) < tercile_size:
            idx += test_days
            continue

        top_stocks = scores.nlargest(tercile_size).index.tolist()

        end_idx = min(idx + test_days, len(all_dates))
        oos_period = daily_returns.iloc[idx+1:end_idx]

        if not oos_period.empty:
            oos_ew = oos_period[top_stocks].mean(axis=1)
            cost = cost_bps / 10000
            oos_ew.iloc[0] -= cost
            oos_returns.append(oos_ew)

        idx += test_days

    if not oos_returns:
        return None
    combined = pd.concat(oos_returns)
    return combined

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
    p_value = np.mean(diffs <= 0)

    return {
        'observed_diff': round(observed_diff, 4),
        'ci_95_low': round(ci_low, 4),
        'ci_95_high': round(ci_high, 4),
        'p_value': round(p_value, 4),
        'significant': ci_low > 0
    }

def survivorship_bias_check(close, valid_tickers):
    total_returns = {}
    for t in valid_tickers:
        s = close[t].dropna()
        if len(s) > 252:
            total_returns[t] = s.iloc[-1] / s.iloc[0] - 1

    sorted_tickers = sorted(total_returns.items(), key=lambda x: x[1], reverse=True)
    top3 = [t for t, _ in sorted_tickers[:3]]
    top3_returns = [(t, round(r*100, 1)) for t, r in sorted_tickers[:3]]

    return top3, top3_returns

def main():
    results = {}

    close, valid_tickers = download_data()
    results['valid_tickers'] = valid_tickers
    results['n_valid'] = len(valid_tickers)
    results['date_range'] = f"{close.index[0].strftime('%Y-%m-%d')} to {close.index[-1].strftime('%Y-%m-%d')}"
    results['n_trading_days'] = len(close)

    print(f"\n{'='*80}", file=sys.stderr)
    print(f"MIDCAP MOMENTUM STUDY", file=sys.stderr)
    print(f"Universe: {len(valid_tickers)} stocks, {results['date_range']}", file=sys.stderr)
    print(f"{'='*80}\n", file=sys.stderr)

    ew_returns = run_equal_weight(close)
    ew_metrics = compute_metrics(ew_returns, "Equal Weight (Benchmark)")
    results['equal_weight'] = ew_metrics
    print(f"EW Benchmark: Sharpe={ew_metrics['sharpe']}, Return={ew_metrics['ann_return']}%", file=sys.stderr)

    strategies = {}
    for lookback, name in [(12, '12-1'), (6, '6-1'), (3, '3-1')]:
        print(f"\nRunning {name} momentum...", file=sys.stderr)

        for cost in [0, 15, 25, 40]:
            result = run_momentum_strategy(close, lookback, skip_months=1, cost_bps=cost)
            if result is None:
                continue
            strat_returns, avg_turnover = result
            key = f"{name}_cost{cost}bps"
            metrics = compute_metrics(strat_returns, f"{name} Momentum ({cost}bps)")
            if metrics:
                metrics['avg_turnover'] = round(avg_turnover * 100, 1)
                strategies[key] = metrics
                if cost == 0:
                    strategies[f"{name}_returns"] = strat_returns
                print(f"  {key}: Sharpe={metrics['sharpe']}, Return={metrics['ann_return']}%, Turnover={metrics['avg_turnover']}%", file=sys.stderr)

    results['strategies'] = {k: v for k, v in strategies.items() if not isinstance(v, pd.Series)}

    print(f"\n== Walk-Forward OOS ==", file=sys.stderr)
    wf_results = {}
    for lookback, name in [(12, '12-1'), (6, '6-1'), (3, '3-1')]:
        for cost in [0, 15, 25, 40]:
            wf_returns = walk_forward_oos(close, lookback, cost_bps=cost)
            if wf_returns is not None:
                wf_metrics = compute_metrics(wf_returns, f"WF {name} ({cost}bps)")
                key = f"wf_{name}_cost{cost}bps"
                wf_results[key] = wf_metrics
                if cost == 0:
                    wf_results[f"wf_{name}_returns"] = wf_returns
                print(f"  {key}: Sharpe={wf_metrics['sharpe']}", file=sys.stderr)

    results['walk_forward'] = {k: v for k, v in wf_results.items() if not isinstance(v, pd.Series)}

    wf_ew = walk_forward_oos(close, 12, cost_bps=0)
    if wf_ew is None:
        wf_ew = ew_returns

    print(f"\n== Bootstrap 95% CI (Sharpe diff vs EW) ==", file=sys.stderr)
    bootstrap_results = {}
    for lookback, name in [(12, '12-1'), (6, '6-1'), (3, '3-1')]:
        key = f"{name}_returns"
        if key in strategies:
            bs = bootstrap_sharpe_diff(strategies[key], ew_returns)
            bootstrap_results[name] = bs
            print(f"  {name}: diff={bs['observed_diff']}, CI=[{bs['ci_95_low']}, {bs['ci_95_high']}], sig={bs['significant']}", file=sys.stderr)

        wf_key = f"wf_{name}_returns"
        if wf_key in wf_results:
            bs_wf = bootstrap_sharpe_diff(wf_results[wf_key], ew_returns)
            bootstrap_results[f"wf_{name}"] = bs_wf
            print(f"  WF {name}: diff={bs_wf['observed_diff']}, CI=[{bs_wf['ci_95_low']}, {bs_wf['ci_95_high']}], sig={bs_wf['significant']}", file=sys.stderr)

    results['bootstrap'] = bootstrap_results

    print(f"\n== Survivorship Bias Check ==", file=sys.stderr)
    top3, top3_returns = survivorship_bias_check(close, valid_tickers)
    results['top3_performers'] = top3_returns
    print(f"  Top 3 performers: {top3_returns}", file=sys.stderr)

    reduced_tickers = [t for t in valid_tickers if t not in top3]
    close_reduced = close[reduced_tickers]

    ew_reduced = run_equal_weight(close_reduced)
    ew_reduced_metrics = compute_metrics(ew_reduced, "EW (Top 3 Removed)")
    results['ew_reduced'] = ew_reduced_metrics

    surv_strategies = {}
    for lookback, name in [(12, '12-1'), (6, '6-1'), (3, '3-1')]:
        result = run_momentum_strategy(close_reduced, lookback, skip_months=1, cost_bps=0)
        if result:
            strat_returns, avg_turnover = result
            metrics = compute_metrics(strat_returns, f"{name} (Reduced)")
            if metrics:
                metrics['avg_turnover'] = round(avg_turnover * 100, 1)
                surv_strategies[name] = metrics
                print(f"  {name} reduced: Sharpe={metrics['sharpe']}, Return={metrics['ann_return']}%", file=sys.stderr)

    results['survivorship_check'] = surv_strategies
    results['ew_reduced'] = ew_reduced_metrics

    bs_reduced = {}
    for lookback, name in [(12, '12-1'), (6, '6-1'), (3, '3-1')]:
        result = run_momentum_strategy(close_reduced, lookback, skip_months=1, cost_bps=0)
        if result:
            strat_returns, _ = result
            bs = bootstrap_sharpe_diff(strat_returns, ew_reduced)
            bs_reduced[name] = bs
            print(f"  {name} reduced bootstrap: diff={bs['observed_diff']}, CI=[{bs['ci_95_low']}, {bs['ci_95_high']}]", file=sys.stderr)
    results['bootstrap_reduced'] = bs_reduced

    print(json.dumps({k: v for k, v in results.items() if not isinstance(v, pd.Series)}, indent=2, default=str))

if __name__ == '__main__':
    main()
