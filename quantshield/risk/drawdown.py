import numpy as np
import pandas as pd


def compute_drawdown_status(
    returns: pd.DataFrame,
    weights: pd.Series,
    max_drawdown_tolerance: float = 0.50,
    days: int = 252,
) -> dict:
    bt = returns.iloc[-days:]
    port_daily = (bt * weights).sum(axis=1).values
    port_value = np.cumprod(np.concatenate(([1.0], 1.0 + port_daily)))

    running_max = np.maximum.accumulate(port_value)
    drawdowns = (port_value - running_max) / running_max
    current_dd = float(drawdowns[-1])
    max_dd = float(drawdowns.min())

    if current_dd < -max_drawdown_tolerance:
        status = 'CRITICAL'
    elif current_dd < -0.30:
        status = 'CAUTION'
    else:
        status = 'NORMAL'

    return {
        'static_weight_drawdown_pct': round(current_dd * 100, 2),
        'max_historical_drawdown_pct': round(max_dd * 100, 2),
        'status': status,
    }
