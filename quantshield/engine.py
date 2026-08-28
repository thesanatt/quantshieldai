import argparse
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yfinance as yf

from quantshield.config import MARKETS, MarketConfig
from quantshield.paths import DASHBOARD
from quantshield.research.backtest import (
    _daily_rf,
    backtest,
    regime_conditional_performance,
    walk_forward_backtest,
)
from quantshield.research.portfolio import build_weights
from quantshield.risk.correlation import correlation_monitor
from quantshield.risk.cvar import compute_portfolio_cvar
from quantshield.risk.deflated_sharpe import deflated_sharpe_ratio
from quantshield.signals.fama_french import decompose_returns
from quantshield.signals.regime import india_detect_regime, us_detect_regime
from quantshield.utils import atomic_write_json, log, sanitize

REGIME_DETECTORS = {'us': us_detect_regime, 'india': india_detect_regime}
LAGGED_MACRO = frozenset({'CL=F', 'USDINR=X'})
HISTORY_DAYS = 2520
MIN_COVERAGE = 0.8
SIGNAL_KEYS = ('momentum', 'vol_adj_momentum', 'mean_reversion', 'trend', 'cross_asset')
CORRELATION_WARNING = 0.6
MIN_FACTOR_MONTHS = 12
MIN_MONTH_SESSIONS = 15


def _close_frame(raw: pd.DataFrame) -> pd.DataFrame:
    frame = raw['Close'] if isinstance(raw.columns, pd.MultiIndex) else raw
    if isinstance(frame, pd.Series):
        frame = frame.to_frame()
    coverage = frame.notna().mean()
    sparse = coverage[coverage < MIN_COVERAGE]
    if len(sparse):
        detail = ', '.join(f'{t} {c:.0%}' for t, c in sparse.items())
        log(f'dropping tickers with coverage below {MIN_COVERAGE:.0%}: {detail}', 'engine')
    return frame.drop(columns=sparse.index).ffill().dropna()


def _download(tickers: tuple[str, ...], start: datetime, end: datetime) -> pd.DataFrame:
    raw = yf.download(list(tickers), start=start, end=end, auto_adjust=True, progress=False)
    if raw is None or raw.empty:
        raise RuntimeError(f'empty download for {list(tickers)}')
    frame = _close_frame(raw)
    if frame.empty:
        raise RuntimeError(f'no usable rows for {list(tickers)}')
    return frame


def _lag_after_hours(macro_close: pd.DataFrame) -> pd.DataFrame:
    lagged = macro_close.copy()
    for col in LAGGED_MACRO.intersection(lagged.columns):
        lagged[col] = lagged[col].shift(1)
    return lagged.dropna()


def download_data(
    cfg: MarketConfig, days: int = HISTORY_DAYS,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.Series]:
    end = datetime.now()
    start = end - timedelta(days=days)
    close = _download(cfg.tickers, start, end)
    if len(close.columns) < 2:
        raise RuntimeError('fewer than two tickers with usable data')
    returns = close.pct_change().dropna()
    benchmark_close = _download((cfg.benchmark,), start, end).iloc[:, 0]
    benchmark_returns = benchmark_close.pct_change().dropna()
    macro_close = _lag_after_hours(_download(cfg.macro_tickers, start, end))
    log(f'{cfg.market}: {len(close)} sessions, {len(close.columns)} tickers, '
        f'{close.index[0].date()} to {close.index[-1].date()}', 'engine')
    return close, returns, macro_close, benchmark_returns


def _round_pct(weights: pd.Series, decimals: int = 2) -> pd.Series:
    scale = 10 ** decimals
    raw = weights * 100.0 * scale
    floored = np.floor(raw)
    short = int(round(100.0 * scale - floored.sum()))
    bumped = floored.values.copy()
    if short > 0:
        bumped[np.argsort(-(raw - floored).values)[:short]] += 1
    return pd.Series(bumped / scale, index=weights.index)


def _weight_rows(
    weights: pd.Series, close: pd.DataFrame, details: dict[str, Any],
) -> list[dict[str, Any]]:
    signals = details['signals']
    table = pd.DataFrame({
        'weight_pct': _round_pct(weights),
        'price': close.iloc[-1].round(2),
        **{k: signals[k].reindex(weights.index).fillna(0.0).round(3) for k in SIGNAL_KEYS},
        'composite': details['composite'].reindex(weights.index).fillna(0.0).round(3),
        'beta': details['betas'].reindex(weights.index).fillna(1.0).round(2),
    })
    table = table.sort_values('weight_pct', ascending=False).rename_axis('ticker').reset_index()
    return table.to_dict('records')


def calendar_month_returns(daily: pd.Series, min_sessions: int = MIN_MONTH_SESSIONS) -> pd.Series:
    monthly = (1.0 + daily).resample('ME').prod() - 1.0
    sessions = daily.resample('ME').size()
    return monthly[sessions >= min_sessions]


def _factor_decomposition(daily: pd.Series) -> dict[str, Any] | None:
    monthly = calendar_month_returns(daily)
    if len(monthly) < MIN_FACTOR_MONTHS:
        return None
    result = decompose_returns(monthly)
    if 'error' in result or result.get('is_synthetic'):
        log('factor decomposition omitted: no real factor data', 'engine')
        return None
    return result


def run(cfg: MarketConfig, skip_walk_forward: bool = False) -> dict[str, Any]:
    close, returns, macro_close, benchmark_returns = download_data(cfg)
    detect_regime = REGIME_DETECTORS[cfg.market]

    regime, confidence, regime_details = detect_regime(macro_close)
    log(f'regime {regime} (confidence {confidence:.2f}), vix {regime_details.get("vix_current")}', 'engine')

    weights, details = build_weights(close, returns, macro_close, benchmark_returns, cfg, regime)
    daily_rf = _daily_rf(macro_close, cfg.risk_free_annual)
    in_sample = backtest(
        returns, weights, macro_close, benchmark_returns=benchmark_returns,
        total_capital=cfg.notional_capital, daily_rf=daily_rf,
    )
    cvar = compute_portfolio_cvar(weights, returns, confidence=cfg.cvar_confidence)
    avg_corr, top_pairs = correlation_monitor(returns)

    output: dict[str, Any] = {
        'market': cfg.market,
        'generated': datetime.now().strftime('%Y-%m-%d'),
        'currency': cfg.currency,
        'benchmark': {'ticker': cfg.benchmark, 'label': cfg.benchmark_label},
        'universe': list(close.columns),
        'regime': {
            'detected': regime,
            'confidence': round(float(confidence), 3),
            'vix': regime_details.get('vix_current'),
            'signal_weights': dict(cfg.regime_weights[regime]),
        },
        'weights': _weight_rows(weights, close, details),
        'walk_forward': None,
        'deflated_sharpe': None,
        'in_sample': {k: in_sample[k] for k in (
            'port_return', 'bench_return', 'alpha', 'port_sharpe', 'bench_sharpe', 'port_maxdd', 'bench_maxdd',
        )},
        'cvar': {
            'portfolio_cvar': cvar['portfolio_cvar'],
            'var': cvar['var'],
            'confidence': cfg.cvar_confidence,
        },
        'correlation': {
            'avg_30d': avg_corr,
            'warning': bool(avg_corr > CORRELATION_WARNING),
            'top_pairs': top_pairs,
        },
        'risk_limits': {
            'min_weight': cfg.min_weight,
            'max_weight': cfg.max_weight,
            'max_single_stock': cfg.max_single_stock,
            'max_sector': cfg.max_sector_pct,
            'max_portfolio_beta': cfg.max_portfolio_beta,
            'max_monthly_cvar': cfg.max_monthly_cvar,
        },
    }

    if skip_walk_forward:
        return output

    wf = walk_forward_backtest(close, returns, macro_close, benchmark_returns, cfg, detect_regime)
    if wf is None:
        return output
    wf_daily = wf.pop('daily_returns')
    wf['regime_performance'] = regime_conditional_performance(wf)
    output['walk_forward'] = wf
    output['deflated_sharpe'] = deflated_sharpe_ratio(
        wf['port_sharpe'], wf['bench_sharpe'], cfg.dsr_trials, wf_daily,
    )
    if cfg.market == 'us':
        factors = _factor_decomposition(wf_daily)
        if factors is not None:
            output['fama_french'] = factors
    return output


def main() -> None:
    parser = argparse.ArgumentParser(prog='python -m quantshield.engine')
    parser.add_argument('--market', choices=sorted(MARKETS), required=True)
    parser.add_argument('--skip-walk-forward', action='store_true')
    parser.add_argument('--out', type=Path, default=None)
    args = parser.parse_args()

    cfg = MARKETS[args.market]
    output = sanitize(run(cfg, skip_walk_forward=args.skip_walk_forward))
    out_path = args.out or DASHBOARD / 'src' / 'data' / f'{cfg.market}.json'
    atomic_write_json(out_path, output)
    log(f'wrote {out_path}', 'engine')
    print(json.dumps(output, indent=2))


if __name__ == '__main__':
    main()
