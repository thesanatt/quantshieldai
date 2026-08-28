
import numpy as np
import pandas as pd

from quantshield.utils import rank_normalize

BETA_WINDOW = 126


def _market_betas(returns: pd.DataFrame, benchmark_returns: pd.Series | None, window: int = BETA_WINDOW) -> pd.Series:
    fallback = pd.Series(1.0, index=returns.columns)
    if benchmark_returns is None or len(benchmark_returns) < window:
        return fallback
    common = returns.index.intersection(benchmark_returns.index)
    stock = returns.loc[common].iloc[-window:].to_numpy(dtype=float)
    mkt = benchmark_returns.loc[common].iloc[-window:].to_numpy(dtype=float)
    n = len(mkt)
    if n < 2:
        return fallback
    mkt_dev = mkt - mkt.mean()
    mkt_var = mkt_dev @ mkt_dev / (n - 1)
    if not mkt_var > 0:
        return fallback
    cov = (stock - stock.mean(axis=0)).T @ mkt_dev / (n - 1)
    return pd.Series(cov / mkt_var, index=returns.columns)


def _sector_mask(columns: pd.Index, members: list[str]) -> pd.Series:
    return pd.Series(columns.isin(members).astype(float), index=columns)


def us_cross_asset_signals(
    close: pd.DataFrame,
    macro_close: pd.DataFrame,
    returns: pd.DataFrame,
    benchmark_returns: pd.Series | None = None,
) -> tuple[pd.Series, pd.Series]:
    betas = _market_betas(returns, benchmark_returns)
    gate = False
    if '^VIX' in macro_close.columns:
        gate |= bool(macro_close['^VIX'].iloc[-1] > 18)
    if '^TNX' in macro_close.columns and len(macro_close) >= 63:
        tnx = macro_close['^TNX']
        gate |= bool((tnx.iloc[-1] - tnx.iloc[-63]) / (tnx.iloc[-63] + 1e-8) > 0.05)
    if 'USO' in macro_close.columns and len(macro_close) >= 21:
        uso = macro_close['USO']
        gate |= bool(uso.iloc[-1] / uso.iloc[-21] - 1 > 0.05)
    if not gate:
        return pd.Series(0.0, index=close.columns), betas
    return rank_normalize(-betas.reindex(close.columns)), betas


def india_cross_asset_signals(
    close: pd.DataFrame,
    macro_close: pd.DataFrame,
    returns: pd.DataFrame,
    benchmark_returns: pd.Series | None = None,
    sector_map: dict[str, list[str]] | None = None,
) -> tuple[pd.Series, pd.Series]:
    betas = _market_betas(returns, benchmark_returns)
    sectors = sector_map or {}
    it_mask = _sector_mask(close.columns, sectors.get('it_exporters', []))
    consumer_mask = _sector_mask(close.columns, sectors.get('consumer', []))
    bank_mask = _sector_mask(close.columns, sectors.get('banks', []))
    signals = pd.Series(0.0, index=close.columns)

    if 'USDINR=X' in macro_close.columns and len(macro_close) >= 21:
        usdinr = macro_close['USDINR=X']
        rupee_change = usdinr.iloc[-1] / usdinr.iloc[-21] - 1
        signals += it_mask * np.clip(rupee_change * 10, -1, 1) * 0.4
        signals += consumer_mask * np.clip(-rupee_change * 8, -1, 1) * 0.3

    if 'CL=F' in macro_close.columns and len(macro_close) >= 21:
        oil = macro_close['CL=F']
        oil_ret = oil.iloc[-1] / oil.iloc[-21] - 1
        if oil_ret > 0.03:
            base_impact = np.clip(-oil_ret * 3, -1, 1) * 0.3
            signals += (1.0 + consumer_mask * 0.5) * base_impact

    if '^NSEI' in macro_close.columns and len(macro_close) >= 63:
        nifty = macro_close['^NSEI']
        if nifty.iloc[-1] / nifty.iloc[-63] - 1 < -0.05:
            signals += bank_mask * -0.3

    if signals.std() > 0:
        signals = signals / (signals.abs().max() + 1e-8)
    return signals.clip(-1, 1), betas
