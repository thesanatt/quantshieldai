import numpy as np
import pandas as pd


def momentum_signal(prices: pd.DataFrame, lookback: int = 252, skip: int = 21) -> pd.Series:
    if len(prices) < lookback + skip:
        return pd.Series(0.0, index=prices.columns)
    window = prices.iloc[-(lookback + skip):-skip]
    return window.iloc[-1] / window.iloc[0] - 1


def vol_adj_momentum(returns: pd.DataFrame, lookback: int = 252, vol_window: int = 63) -> pd.Series:
    if len(returns) < lookback:
        return pd.Series(0.0, index=returns.columns)
    cum_ret = (1 + returns.iloc[-lookback:]).prod() - 1
    recent_vol = returns.iloc[-vol_window:].std() * np.sqrt(252)
    vol_adj = cum_ret / recent_vol.replace(0, np.nan)
    return (vol_adj.rank(pct=True) * 2 - 1).fillna(0.0)
