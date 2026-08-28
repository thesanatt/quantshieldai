import numpy as np
import pandas as pd


def _tail(port_returns: pd.Series, confidence: float) -> tuple[float, pd.Series]:
    var_val = float(np.percentile(port_returns, (1.0 - confidence) * 100))
    return var_val, port_returns <= var_val


def compute_portfolio_cvar(
    weights: pd.Series,
    returns: pd.DataFrame,
    confidence: float = 0.95,
) -> dict:
    aligned = returns[weights.index].dropna()
    if len(aligned) < 5:
        return {
            'portfolio_cvar': 0.0,
            'var': 0.0,
            'component_cvar': {},
            'confidence': confidence,
        }

    port_returns = (aligned * weights).sum(axis=1)
    var_val, tail_mask = _tail(port_returns, confidence)

    if not tail_mask.any():
        portfolio_cvar = var_val
        component = pd.Series(0.0, index=weights.index)
    else:
        portfolio_cvar = float(port_returns[tail_mask].mean())
        component = (aligned.loc[tail_mask] * weights).mean()

    return {
        'portfolio_cvar': round(float(portfolio_cvar), 8),
        'var': round(var_val, 8),
        'component_cvar': component.round(8).astype(float).to_dict(),
        'confidence': confidence,
    }


def apply_cvar_constraint(
    weights: pd.Series,
    returns: pd.DataFrame,
    max_monthly_cvar: float = 0.03,
    confidence: float = 0.95,
) -> pd.Series:
    adjusted = weights.copy()
    monthly = ((1.0 + returns[adjusted.index]).resample('ME').prod() - 1.0).dropna()

    if len(monthly) < 5:
        return adjusted

    for _ in range(20):
        port_monthly = (monthly * adjusted).sum(axis=1)
        _, tail_mask = _tail(port_monthly, confidence)
        if not tail_mask.any():
            break

        cvar = float(port_monthly[tail_mask].mean())
        if cvar >= -max_monthly_cvar:
            break

        component = (monthly.loc[tail_mask] * adjusted).mean()
        worst = component.idxmin()
        best = component.idxmax()

        reduction = adjusted[worst] * 0.10
        adjusted[worst] -= reduction
        adjusted[best] += reduction

        adjusted = adjusted.clip(lower=0.0)
        total = adjusted.sum()
        if total > 0:
            adjusted = adjusted / total

    return adjusted
