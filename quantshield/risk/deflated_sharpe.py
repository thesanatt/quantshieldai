import numpy as np
import pandas as pd
from scipy.stats import norm

EULER_MASCHERONI = 0.5772156649015329


def expected_max_sharpe(n_trials: int, var_sharpe: float) -> float:
    if n_trials <= 1 or var_sharpe <= 0.0:
        return 0.0
    z_upper = norm.ppf(1.0 - 1.0 / n_trials)
    z_lower = norm.ppf(1.0 - 1.0 / (n_trials * np.e))
    e_max_z = (1.0 - EULER_MASCHERONI) * z_upper + EULER_MASCHERONI * z_lower
    return float(np.sqrt(var_sharpe) * e_max_z)


def sharpe_std_error(sr: float, skewness: float, kurtosis: float, t_obs: int) -> float:
    if t_obs <= 1:
        return float('nan')
    numerator = 1.0 - skewness * sr + (kurtosis - 1.0) / 4.0 * sr ** 2
    return float(np.sqrt(max(numerator, 1e-12) / (t_obs - 1.0)))


def deflated_sharpe_ratio(
    observed_sharpe_annual: float,
    benchmark_sharpe_annual: float,
    n_trials: int,
    returns: pd.Series,
    periods_per_year: int = 252,
) -> dict:
    clean = returns.dropna()
    t_obs = int(len(clean))
    scale = float(np.sqrt(periods_per_year))

    if t_obs < 10:
        return {
            'observed_sharpe_annual': float(observed_sharpe_annual),
            'benchmark_sharpe_annual': float(benchmark_sharpe_annual),
            'expected_max_sharpe_annual': None,
            'sr_star_annual': None,
            'psr': None,
            'p_value': None,
            'is_significant': False,
            'n_trials': int(n_trials),
            't_obs': t_obs,
            'skewness': None,
            'excess_kurtosis': None,
            'periods_per_year': int(periods_per_year),
            'error': 'insufficient_data',
        }

    sr = float(observed_sharpe_annual) / scale
    sr_bench = float(benchmark_sharpe_annual) / scale
    skewness = float(clean.skew())
    kurtosis = float(clean.kurtosis()) + 3.0

    sr_std = sharpe_std_error(sr, skewness, kurtosis, t_obs)
    e_max = expected_max_sharpe(n_trials, sr_std ** 2)
    sr_star = max(sr_bench, e_max)
    psr = float(norm.cdf((sr - sr_star) / sr_std))
    p_value = 1.0 - psr

    return {
        'observed_sharpe_annual': round(float(observed_sharpe_annual), 6),
        'benchmark_sharpe_annual': round(float(benchmark_sharpe_annual), 6),
        'expected_max_sharpe_annual': round(e_max * scale, 6),
        'sr_star_annual': round(sr_star * scale, 6),
        'psr': round(psr, 6),
        'p_value': round(p_value, 6),
        'is_significant': bool(p_value < 0.05),
        'n_trials': int(n_trials),
        't_obs': t_obs,
        'skewness': round(skewness, 6),
        'excess_kurtosis': round(kurtosis - 3.0, 6),
        'periods_per_year': int(periods_per_year),
    }
