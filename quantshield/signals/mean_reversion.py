import pandas as pd


def rsi_signal(prices: pd.DataFrame, period: int = 14) -> pd.Series:
    ret = prices.pct_change()
    gain = ret.where(ret > 0, 0.0).rolling(period).mean().iloc[-1]
    loss = (-ret.where(ret < 0, 0.0)).rolling(period).mean().iloc[-1]
    rs = gain / loss.replace(0, 1e-10)
    rsi = 100 - (100 / (1 + rs))
    signal = ((50 - rsi) / 50).where((gain + loss) > 0, 0.0)
    return signal.clip(-1, 1)
