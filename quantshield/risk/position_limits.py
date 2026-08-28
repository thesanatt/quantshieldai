import pandas as pd

from quantshield.utils import log


def apply_sector_limits(
    weights: pd.Series,
    sector_map: dict[str, list[str]],
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
    if total > 0:
        adjusted = adjusted / total
    return adjusted


def estimate_betas(
    tickers: pd.Index,
    returns: pd.DataFrame,
    benchmark_returns: pd.Series | None,
    window: int = 252,
    min_obs: int = 63,
) -> pd.Series:
    betas = pd.Series(1.0, index=tickers)
    if benchmark_returns is None:
        return betas
    present = [t for t in tickers if t in returns.columns]
    if not present:
        return betas
    x = returns[present].iloc[-window:]
    b = benchmark_returns.iloc[-window:]
    common = x.index.intersection(b.index)
    frame = x.reindex(common).join(b.reindex(common).rename('_bm')).dropna()
    if len(frame) < min_obs:
        return betas
    bm = frame['_bm']
    bm_var = float(bm.var())
    if bm_var <= 1e-10:
        return betas
    cov = frame[present].sub(frame[present].mean()).mul(bm - bm.mean(), axis=0).sum() / (len(frame) - 1)
    betas[present] = (cov / bm_var).clip(0.0, 5.0)
    return betas


def _cap_single_names(adjusted: pd.Series, max_single_stock: float, breached: list[str]) -> pd.Series:
    for _ in range(10):
        over_mask = adjusted > max_single_stock + 1e-8
        if not over_mask.any():
            break
        breached.extend(
            f"{t} capped from {adjusted[t] * 100:.1f}% to {max_single_stock * 100:.0f}%"
            for t in adjusted[over_mask].index
        )
        total_excess = (adjusted[over_mask] - max_single_stock).sum()
        adjusted[over_mask] = max_single_stock
        under_mask = adjusted < max_single_stock - 1e-8
        if under_mask.any():
            room = max_single_stock - adjusted[under_mask]
            total_room = room.sum()
            if total_room > 0:
                adjusted[under_mask] += room / total_room * min(total_excess, total_room)
    return adjusted / adjusted.sum()


def _cap_beta(adjusted: pd.Series, betas: pd.Series, max_portfolio_beta: float) -> pd.Series:
    if float(betas.min()) > max_portfolio_beta:
        inv_beta = 1.0 / betas
        return inv_beta / inv_beta.sum()
    inv_beta_sq = 1.0 / betas ** 2
    target = inv_beta_sq / inv_beta_sq.sum()
    lo, hi = 0.0, 1.0
    for _ in range(100):
        mid = (lo + hi) / 2
        candidate = (1 - mid) * adjusted + mid * target
        candidate = candidate / candidate.sum()
        if float((candidate * betas).sum()) > max_portfolio_beta:
            lo = mid
        else:
            hi = mid
    result = (1 - hi) * adjusted + hi * target
    return result / result.sum()


def apply_position_limits(
    weights: pd.Series,
    returns: pd.DataFrame,
    benchmark_returns: pd.Series | None = None,
    max_single_stock: float = 0.25,
    max_portfolio_beta: float = 1.5,
) -> tuple[pd.Series, dict]:
    breached: list[str] = []
    adjusted = _cap_single_names(weights.copy(), max_single_stock, breached)

    betas = estimate_betas(adjusted.index, returns, benchmark_returns)
    portfolio_beta = float((adjusted * betas).sum())

    if portfolio_beta > max_portfolio_beta:
        original_beta = portfolio_beta
        adjusted = _cap_beta(adjusted, betas, max_portfolio_beta)
        portfolio_beta = float((adjusted * betas).sum())
        breached.append(f"Portfolio beta scaled from {original_beta:.2f} to {portfolio_beta:.2f}")

    for msg in breached:
        log(f"  POSITION LIMIT: {msg}")

    risk_limits = {
        'max_single_stock_pct': round(float(adjusted.max()) * 100, 1),
        'portfolio_beta': round(portfolio_beta, 2),
        'limits_breached': breached,
    }
    return adjusted, risk_limits
