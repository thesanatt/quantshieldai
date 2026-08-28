import numpy as np
import pandas as pd


def correlation_monitor(returns: pd.DataFrame, window: int = 30) -> tuple[float, list[dict]]:
    corr = returns.iloc[-window:].corr()
    n = len(corr)
    if n <= 1:
        return 0.0, []

    vals = corr.values
    cols = corr.columns
    triu_i, triu_j = np.triu_indices(n, k=1)
    corr_vals = vals[triu_i, triu_j]
    avg_corr = float(corr_vals.mean())
    top_idx = np.argsort(-np.abs(corr_vals))[:5]
    pairs = [
        {'pair': f"{cols[triu_i[k]]}/{cols[triu_j[k]]}", 'corr': round(float(corr_vals[k]), 3)}
        for k in top_idx
    ]
    return round(avg_corr, 3), pairs
