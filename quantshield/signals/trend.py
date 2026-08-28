import pandas as pd


def trend_signal(prices: pd.DataFrame) -> pd.Series:
    if len(prices) < 200:
        return pd.Series(0.0, index=prices.columns)
    sma50 = prices.rolling(50).mean().iloc[-1]
    sma200 = prices.rolling(200).mean().iloc[-1]
    current = prices.iloc[-1]
    score = (
        (current > sma200).astype(float) * 0.5
        + (current > sma50).astype(float) * 0.3
        + (sma50 > sma200).astype(float) * 0.2
    )
    return score * 2 - 1
