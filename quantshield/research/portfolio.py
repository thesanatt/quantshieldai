from typing import Any

import pandas as pd

from quantshield.config import MarketConfig
from quantshield.risk.cvar import apply_cvar_constraint
from quantshield.risk.hrp import hrp_weights
from quantshield.risk.position_limits import apply_position_limits, apply_sector_limits
from quantshield.signals.composite import composite_score, compute_signals

LIMIT_PASSES = 10
LIMIT_TOL = 1e-6


def within_limits(weights: pd.Series, cfg: MarketConfig, tol: float = LIMIT_TOL) -> bool:
    cap = min(cfg.max_weight, cfg.max_single_stock)
    if (weights < cfg.min_weight - tol).any() or (weights > cap + tol).any():
        return False
    sector_totals = pd.Series(
        {sector: weights.reindex(members).sum() for sector, members in cfg.sector_map.items()}
    )
    return bool((sector_totals <= cfg.max_sector_pct + tol).all())


def enforce_limits(
    weights: pd.Series,
    returns: pd.DataFrame,
    benchmark_returns: pd.Series | None,
    cfg: MarketConfig,
) -> tuple[pd.Series, dict[str, Any]]:
    limits: dict[str, Any] = {}
    for _ in range(LIMIT_PASSES):
        weights = weights.clip(lower=cfg.min_weight, upper=cfg.max_weight)
        weights = weights / weights.sum()
        weights = apply_sector_limits(weights, cfg.sector_map, cfg.max_sector_pct)
        weights, limits = apply_position_limits(
            weights, returns, benchmark_returns=benchmark_returns,
            max_single_stock=cfg.max_single_stock, max_portfolio_beta=cfg.max_portfolio_beta,
        )
        if within_limits(weights, cfg):
            break
    return weights, limits


def build_weights(
    train_close: pd.DataFrame,
    train_returns: pd.DataFrame,
    train_macro: pd.DataFrame,
    train_bm: pd.Series | None,
    cfg: MarketConfig,
    regime: str,
) -> tuple[pd.Series, dict[str, Any]]:
    signals, betas = compute_signals(
        train_close, train_macro, train_returns, train_bm, cfg.market, regime, cfg.sector_map,
    )
    signal_weights = cfg.regime_weights[regime]
    composite = composite_score(signals, signal_weights)
    signal_tilt = composite.rank(pct=True)
    signal_tilt = signal_tilt / signal_tilt.sum()

    hrp = hrp_weights(train_returns).reindex(train_close.columns)
    blended = (1 - cfg.tilt_strength) * hrp + cfg.tilt_strength * signal_tilt.reindex(train_close.columns)

    weights, _ = enforce_limits(blended, train_returns, train_bm, cfg)
    weights = apply_cvar_constraint(
        weights, train_returns, max_monthly_cvar=cfg.max_monthly_cvar, confidence=cfg.cvar_confidence,
    )
    weights, limits = enforce_limits(weights, train_returns, train_bm, cfg)
    weights = weights.reindex(train_close.columns)

    details = {
        'signals': signals,
        'betas': betas,
        'composite': composite,
        'hrp': hrp,
        'signal_weights': signal_weights,
        'risk_limits': limits,
    }
    return weights, details
