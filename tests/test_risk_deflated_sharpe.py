import numpy as np
import pandas as pd
import pytest
from scipy.stats import norm

from quantshield.risk.deflated_sharpe import (
    EULER_MASCHERONI,
    deflated_sharpe_ratio,
    expected_max_sharpe,
    sharpe_std_error,
)


def _daily(sr_annual: float, t_obs: int, seed: int = 0, sigma: float = 0.01) -> pd.Series:
    rng = np.random.default_rng(seed)
    return pd.Series(rng.normal(sr_annual / np.sqrt(252) * sigma, sigma, t_obs))


def _monthly(sr_annual: float, t_obs: int, seed: int = 0, sigma: float = 0.04) -> pd.Series:
    rng = np.random.default_rng(seed)
    return pd.Series(rng.normal(sr_annual / np.sqrt(12) * sigma, sigma, t_obs))


EULER_GAMMA_LITERAL = 0.5772156649


class TestExpectedMaxSharpe:
    @pytest.mark.parametrize('n_trials,expected', [(2, 0.519755), (10, 1.574598), (100, 2.530603)])
    def test_matches_paper_closed_form(self, n_trials: int, expected: float) -> None:
        closed_form = (
            (1 - EULER_GAMMA_LITERAL) * norm.ppf(1 - 1 / n_trials)
            + EULER_GAMMA_LITERAL * norm.ppf(1 - 1 / (n_trials * np.e))
        )
        assert expected_max_sharpe(n_trials, 1.0) == pytest.approx(expected, abs=1e-6)
        assert expected_max_sharpe(n_trials, 1.0) == pytest.approx(closed_form, abs=1e-8)

    def test_module_constant_is_euler_mascheroni(self) -> None:
        assert EULER_MASCHERONI == pytest.approx(EULER_GAMMA_LITERAL, abs=1e-10)

    def test_scales_with_sharpe_std(self):
        assert expected_max_sharpe(10, 4.0) == pytest.approx(2.0 * expected_max_sharpe(10, 1.0), abs=1e-9)
        assert expected_max_sharpe(100, 0.25) == pytest.approx(0.5 * 2.530603, abs=1e-6)

    def test_single_or_zero_trial_is_zero(self):
        assert expected_max_sharpe(1, 1.0) == 0.0
        assert expected_max_sharpe(0, 1.0) == 0.0

    def test_zero_variance_is_zero(self):
        assert expected_max_sharpe(50, 0.0) == 0.0

    def test_increases_with_trials(self):
        values = [expected_max_sharpe(n, 1.0) for n in (2, 5, 10, 50, 100, 1000)]
        assert all(b > a for a, b in zip(values, values[1:], strict=False))


class TestSharpeStdError:
    def test_normal_iid_reduces_to_one_over_sqrt_t(self):
        assert abs(sharpe_std_error(0.0, 0.0, 3.0, 1001) - 1 / np.sqrt(1000)) < 1e-12

    def test_fat_tails_widen_error(self):
        assert sharpe_std_error(0.1, 0.0, 10.0, 500) > sharpe_std_error(0.1, 0.0, 3.0, 500)

    def test_negative_skew_widens_error(self):
        assert sharpe_std_error(0.1, -1.0, 3.0, 500) > sharpe_std_error(0.1, 0.0, 3.0, 500)


class TestDeflatedSharpeRatio:
    def test_output_keys(self):
        result = deflated_sharpe_ratio(0.4, 0.0, 20, _daily(0.4, 1500))
        expected = {
            'observed_sharpe_annual', 'benchmark_sharpe_annual', 'expected_max_sharpe_annual',
            'sr_star_annual', 'psr', 'p_value', 'is_significant', 'n_trials', 't_obs',
            'skewness', 'excess_kurtosis', 'periods_per_year',
        }
        assert expected == set(result)
        assert result['n_trials'] == 20
        assert result['t_obs'] == 1500
        assert result['periods_per_year'] == 252
        assert abs(result['psr'] + result['p_value'] - 1.0) < 1e-6

    def test_modest_sharpe_after_twenty_trials_is_not_significant(self):
        result = deflated_sharpe_ratio(0.4, 0.0, 20, _daily(0.4, 1500))
        assert result['p_value'] > 0.5
        assert result['is_significant'] is False

    def test_expected_max_is_reported_in_annual_units(self):
        returns = _daily(0.4, 1500)
        result = deflated_sharpe_ratio(0.4, 0.0, 20, returns)
        sr = 0.4 / np.sqrt(252)
        sr_std = sharpe_std_error(sr, float(returns.skew()), float(returns.kurtosis()) + 3.0, 1500)
        assert abs(result['expected_max_sharpe_annual'] - expected_max_sharpe(20, sr_std ** 2) * np.sqrt(252)) < 1e-5

    def test_single_trial_depends_only_on_benchmark(self):
        returns = _daily(0.4, 1500)
        sr = 0.4 / np.sqrt(252)
        sr_std = sharpe_std_error(sr, float(returns.skew()), float(returns.kurtosis()) + 3.0, 1500)
        low = deflated_sharpe_ratio(0.4, 0.0, 1, returns)
        high = deflated_sharpe_ratio(0.4, 0.3, 1, returns)
        assert low['expected_max_sharpe_annual'] == 0.0
        assert high['expected_max_sharpe_annual'] == 0.0
        assert abs(low['p_value'] - (1 - norm.cdf(sr / sr_std))) < 1e-5
        assert abs(high['p_value'] - (1 - norm.cdf((sr - 0.3 / np.sqrt(252)) / sr_std))) < 1e-5
        assert high['p_value'] > low['p_value']

    def test_p_value_monotone_in_trials(self):
        returns = _daily(1.0, 1500)
        p_values = [deflated_sharpe_ratio(1.0, 0.5, n, returns)['p_value'] for n in (1, 2, 5, 10, 20, 50, 100, 1000)]
        assert all(b >= a for a, b in zip(p_values, p_values[1:], strict=False))
        assert p_values[-1] > p_values[0]

    def test_unit_invariance_daily_vs_monthly(self):
        daily = deflated_sharpe_ratio(0.4, 0.0, 17, _daily(0.4, 1500, seed=1))
        monthly = deflated_sharpe_ratio(0.4, 0.0, 17, _monthly(0.4, 72, seed=1), periods_per_year=12)
        assert abs(daily['p_value'] - monthly['p_value']) < 0.15

    def test_higher_sharpe_lower_p_value(self):
        returns = _daily(1.0, 1500)
        weak = deflated_sharpe_ratio(0.5, 0.0, 17, returns)
        strong = deflated_sharpe_ratio(2.0, 0.0, 17, returns)
        assert strong['p_value'] < weak['p_value']

    def test_strong_sharpe_is_significant(self):
        result = deflated_sharpe_ratio(3.0, 0.5, 20, _daily(3.0, 1500))
        assert result['p_value'] < 0.05
        assert result['is_significant'] is True

    def test_insufficient_data(self):
        result = deflated_sharpe_ratio(1.0, 0.5, 10, pd.Series([0.01, 0.02, 0.03]))
        assert result['error'] == 'insufficient_data'
        assert result['is_significant'] is False
        assert result['p_value'] is None
        assert result['t_obs'] == 3

    def test_nans_are_dropped_before_counting(self):
        returns = _daily(0.4, 100)
        returns.iloc[:5] = np.nan
        assert deflated_sharpe_ratio(0.4, 0.0, 5, returns)['t_obs'] == 95

    def test_moments_are_reported(self):
        rng = np.random.default_rng(3)
        returns = pd.Series(rng.standard_t(4, 1000) * 0.01)
        result = deflated_sharpe_ratio(0.5, 0.0, 5, returns)
        assert abs(result['skewness'] - float(returns.skew())) < 1e-5
        assert abs(result['excess_kurtosis'] - float(returns.kurtosis())) < 1e-5
        assert result['excess_kurtosis'] > 0.5
