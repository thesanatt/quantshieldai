
import numpy as np
import pandas as pd
from scipy.stats import linregress, spearmanr

VOL_TARGET_US = 0.15
VOL_TARGET_INDIA = 0.20
VOL_SCALAR_MIN = 0.5
VOL_SCALAR_MAX = 1.5


def vol_target(
    returns: pd.DataFrame,
    weights: pd.Series,
    target_vol: float = 0.15,
    scalar_min: float = 0.5,
    scalar_max: float = 1.5,
    window: int = 63,
) -> pd.Series:
    port_returns = (returns * weights).sum(axis=1)
    if len(port_returns) < window:
        return weights
    realized_vol = port_returns.iloc[-window:].std() * np.sqrt(252)
    if realized_vol < 1e-10:
        return weights
    scalar = float(np.clip(target_vol / realized_vol, scalar_min, scalar_max))
    adjusted = weights * scalar
    return adjusted / adjusted.sum()


def apply_sector_limits_wf(
    weights: pd.Series,
    sector_map: dict[str, list],
    max_sector_pct: float = 0.40,
) -> pd.Series:
    adjusted = weights.copy()
    for _ in range(10):
        excess_found = False
        for members in sector_map.values():
            member_idx = [m for m in members if m in adjusted.index]
            sector_total = adjusted.reindex(member_idx, fill_value=0.0).sum()
            if sector_total > max_sector_pct + 1e-8:
                excess_found = True
                excess = sector_total - max_sector_pct
                adjusted[member_idx] *= max_sector_pct / sector_total
                non_sector = [t for t in adjusted.index if t not in member_idx]
                if non_sector:
                    non_sector_total = adjusted[non_sector].sum()
                    if non_sector_total > 0:
                        adjusted[non_sector] *= (non_sector_total + excess) / non_sector_total
        if not excess_found:
            break
    total = adjusted.sum()
    return adjusted / total if total > 0 else adjusted


def compute_transaction_cost(
    turnover_weights: pd.Series,
    volume_data: pd.DataFrame | None,
    close_data: pd.DataFrame | None,
    returns_data: pd.DataFrame | None,
    spread_bps: float = 5.0,
    impact_k: float = 0.1,
    total_capital: float = 100000,
) -> float:
    if volume_data is None or close_data is None or returns_data is None:
        return float(turnover_weights.abs().sum() * spread_bps / 10000.0)
    total_cost = 0.0
    for ticker in turnover_weights.index:
        trade_weight = abs(float(turnover_weights.get(ticker, 0.0)))
        if trade_weight < 1e-8:
            continue
        impact_cost = 0.0
        if ticker in volume_data.columns and ticker in close_data.columns and ticker in returns_data.columns:
            vol_series = volume_data[ticker].dropna()
            if len(vol_series) >= 21:
                adv_dollar = float(vol_series.iloc[-21:].mean()) * float(close_data[ticker].iloc[-1])
                if adv_dollar > 0:
                    daily_vol = float(returns_data[ticker].iloc[-63:].std()) if len(returns_data[ticker]) >= 63 else 0.02
                    impact_cost = impact_k * np.sqrt(trade_weight * total_capital / adv_dollar) * daily_vol
        total_cost += trade_weight * spread_bps / 10000.0 + impact_cost
    return float(total_cost)


def vix_term_structure_signal(
    close: pd.DataFrame,
    macro_close: pd.DataFrame,
    returns: pd.DataFrame,
    regime: str = 'risk_on',
) -> pd.Series:
    tickers = close.columns
    zeros = pd.Series(0.0, index=tickers)
    if regime == 'risk_on' or '^VIX' not in macro_close.columns or '^VIX3M' not in macro_close.columns:
        return zeros
    vix = macro_close['^VIX']
    vix3m = macro_close['^VIX3M']
    if len(vix) < 63 or len(vix3m) < 63:
        return zeros
    ts_ratio = (vix / vix3m.replace(0, np.nan)).dropna()
    if len(ts_ratio) < 63:
        return zeros
    slope, intercept, _, _, _ = linregress(vix.loc[ts_ratio.index].values, ts_ratio.values)
    residuals = ts_ratio - (intercept + slope * vix.loc[ts_ratio.index])
    fwd = returns.iloc[:, 0].shift(-5)
    common_idx = residuals.index.intersection(fwd.dropna().index)
    if len(common_idx) < 63:
        return zeros
    corr, _ = spearmanr(residuals.loc[common_idx].iloc[-63:].values, fwd.loc[common_idx].iloc[-63:].values)
    if corr < -0.1:
        return zeros
    current_year = pd.Timestamp.now().year
    year_idx = [i for i in common_idx if i.year == current_year - 1]
    if len(year_idx) >= 63:
        _, yr_pval = spearmanr(residuals.loc[year_idx].values, fwd.loc[year_idx].values)
        if yr_pval > 0.05:
            return zeros
    lookback_std = residuals.iloc[-63:].std()
    if lookback_std == 0 or np.isnan(lookback_std):
        return zeros
    z_score = residuals.iloc[-1] / lookback_std
    return pd.Series(float(np.clip(-z_score, -1, 1)), index=tickers)


def copper_gold_signal(
    close: pd.DataFrame,
    macro_close: pd.DataFrame,
    returns: pd.DataFrame,
) -> pd.Series:
    tickers = close.columns
    zeros = pd.Series(0.0, index=tickers)
    if 'HG=F' not in macro_close.columns or 'GC=F' not in macro_close.columns:
        return zeros
    copper = macro_close['HG=F'].dropna()
    gold = macro_close['GC=F'].dropna()
    common_idx = copper.index.intersection(gold.index)
    if len(common_idx) < 63:
        return zeros
    ratio = (copper.loc[common_idx] / gold.loc[common_idx].replace(0, np.nan)).dropna()
    if len(ratio) < 21:
        return zeros
    ratio_ret_21d = ratio.pct_change(21).dropna()
    if len(ratio_ret_21d) < 63:
        return zeros
    residual_series = ratio_ret_21d
    if 'UUP' in macro_close.columns:
        uup_ret_21d = macro_close['UUP'].reindex(ratio_ret_21d.index).dropna().pct_change(21).dropna()
        common = ratio_ret_21d.index.intersection(uup_ret_21d.index)
        if len(common) >= 30:
            slope, intercept, _, _, _ = linregress(uup_ret_21d.loc[common].values, ratio_ret_21d.loc[common].values)
            residual_series = ratio_ret_21d.loc[common] - (intercept + slope * uup_ret_21d.loc[common])
    if len(residual_series) < 63:
        return zeros
    recent = residual_series.iloc[-63:]
    z_score = (residual_series.iloc[-1] - recent.mean()) / (recent.std() + 1e-10)
    signal_value = float(np.clip(-z_score, -1, 1))
    fwd_ret = returns.mean(axis=1).shift(-5)
    common_idx_corr = residual_series.index.intersection(fwd_ret.dropna().index)
    if len(common_idx_corr) >= 63:
        n_negative = 0
        for start in range(max(0, len(common_idx_corr) - 63 * 3), len(common_idx_corr) - 63 + 1, 21):
            window_idx = common_idx_corr[start:start + 63]
            corr, _ = spearmanr(residual_series.loc[window_idx].values, fwd_ret.loc[window_idx].values)
            n_negative = n_negative + 1 if corr < -0.05 else 0
        if n_negative >= 3:
            signal_value = 0.0
    return pd.Series(signal_value, index=tickers)
