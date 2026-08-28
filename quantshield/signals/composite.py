
import pandas as pd

from quantshield.signals.cross_asset import india_cross_asset_signals, us_cross_asset_signals
from quantshield.signals.mean_reversion import rsi_signal
from quantshield.signals.momentum import momentum_signal, vol_adj_momentum
from quantshield.signals.trend import trend_signal
from quantshield.utils import rank_normalize

SIGNAL_KEYS = ['momentum', 'vol_adj_momentum', 'mean_reversion', 'trend', 'cross_asset']


def compute_signals(
    close: pd.DataFrame,
    macro_close: pd.DataFrame,
    returns: pd.DataFrame,
    benchmark_returns: pd.Series | None,
    market: str,
    regime: str,
    sector_map: dict[str, list[str]] | None,
) -> tuple[dict[str, pd.Series], pd.Series]:
    if market == 'india':
        cross_raw, betas = india_cross_asset_signals(
            close, macro_close, returns, benchmark_returns=benchmark_returns, sector_map=sector_map,
        )
    elif market == 'us':
        cross_raw, betas = us_cross_asset_signals(close, macro_close, returns, benchmark_returns=benchmark_returns)
    else:
        raise ValueError(f'unknown market: {market}')
    signals = {
        'momentum': rank_normalize(momentum_signal(close)),
        'vol_adj_momentum': rank_normalize(vol_adj_momentum(returns)),
        'mean_reversion': rank_normalize(rsi_signal(close)),
        'trend': rank_normalize(trend_signal(close)),
        'cross_asset': rank_normalize(cross_raw),
    }
    return signals, betas


def composite_score(signals: dict[str, pd.Series], weights: dict[str, float]) -> pd.Series:
    if not signals:
        raise ValueError('signals is empty')
    total = pd.Series(0.0, index=next(iter(signals.values())).index)
    for key, weight in weights.items():
        if key in signals:
            total = total + weight * signals[key]
    return total
