import json

import numpy as np
import pandas as pd
import pytest

from quantshield.risk.position_limits import apply_position_limits, apply_sector_limits, estimate_betas
from quantshield.utils import sanitize
from tests.conftest import make_returns


def _iid_returns(tickers: list[str], dates: pd.DatetimeIndex, seed: int = 42) -> pd.DataFrame:
    return make_returns(len(dates), tuple(tickers), seed=seed).set_axis(dates)


class TestSectorLimits:
    def test_hand_computed_single_breach(self):
        weights = pd.Series({'A': 0.5, 'B': 0.2, 'C': 0.3})
        result = apply_sector_limits(weights, {'tech': ['A', 'B']}, max_sector_pct=0.40)
        assert result['A'] == pytest.approx(0.4 * 0.5 / 0.7)
        assert result['B'] == pytest.approx(0.4 * 0.2 / 0.7)
        assert result['C'] == pytest.approx(0.6)
        assert result.sum() == pytest.approx(1.0)

    def test_two_breaching_sectors_converge(self):
        weights = pd.Series({'A': 0.3, 'B': 0.3, 'C': 0.2, 'D': 0.15, 'E': 0.05})
        sector_map = {'s1': ['A', 'B'], 's2': ['C', 'D'], 's3': ['E']}
        result = apply_sector_limits(weights, sector_map, max_sector_pct=0.40)
        assert result.sum() == pytest.approx(1.0)
        assert result[['A', 'B']].sum() == pytest.approx(0.40, abs=1e-3)
        assert result[['C', 'D']].sum() == pytest.approx(0.40, abs=1e-3)
        assert result['E'] == pytest.approx(0.20, abs=1e-3)
        assert (result >= 0).all()

    def test_infeasible_caps_stop_after_ten_passes(self):
        weights = pd.Series({'A': 0.5, 'B': 0.5})
        result = apply_sector_limits(weights, {'s1': ['A'], 's2': ['B']}, max_sector_pct=0.40)
        assert result.sum() == pytest.approx(1.0)
        assert (result >= 0).all()

    def test_no_breach_is_identity(self):
        weights = pd.Series({'A': 0.3, 'B': 0.3, 'C': 0.4})
        result = apply_sector_limits(weights, {'s1': ['A'], 's2': ['B'], 's3': ['C']}, max_sector_pct=0.40)
        pd.testing.assert_series_equal(result, weights)

    def test_all_names_in_one_sector_keeps_proportions(self):
        weights = pd.Series({'A': 0.6, 'B': 0.4})
        result = apply_sector_limits(weights, {'only': ['A', 'B']}, max_sector_pct=0.40)
        pd.testing.assert_series_equal(result, weights)

    def test_unknown_tickers_in_sector_map_are_ignored(self):
        weights = pd.Series({'A': 0.5, 'B': 0.5})
        result = apply_sector_limits(weights, {'s': ['A', 'ZZZ']}, max_sector_pct=0.40)
        assert result['A'] == pytest.approx(0.4)
        assert result['B'] == pytest.approx(0.6)

    def test_zero_weights_do_not_divide_by_zero(self):
        weights = pd.Series({'A': 0.0, 'B': 0.0})
        result = apply_sector_limits(weights, {'s': ['A']}, max_sector_pct=0.40)
        assert (result == 0.0).all()

    def test_does_not_mutate_input(self):
        weights = pd.Series({'A': 0.5, 'B': 0.2, 'C': 0.3})
        original = weights.copy()
        apply_sector_limits(weights, {'tech': ['A', 'B']}, max_sector_pct=0.40)
        pd.testing.assert_series_equal(weights, original)


class TestEstimateBetas:
    def test_matches_cov_over_var_on_common_window(self, dates_300):
        rng = np.random.default_rng(5)
        bm = pd.Series(rng.normal(0.001, 0.02, 300), index=dates_300)
        returns = pd.DataFrame({
            'A': bm.values * 2.5 + rng.normal(0, 0.005, 300),
            'B': bm.values * 0.3 + rng.normal(0, 0.005, 300),
        }, index=dates_300)
        betas = estimate_betas(pd.Index(['A', 'B']), returns, bm)
        window = returns.iloc[-252:]
        bm_window = bm.iloc[-252:]
        for t in ['A', 'B']:
            assert betas[t] == pytest.approx(float(window[t].cov(bm_window) / bm_window.var()), abs=1e-12)
        assert betas['A'] > 2.0
        assert betas['B'] < 0.6

    def test_negative_beta_clipped_to_zero_and_high_beta_to_five(self, dates_300):
        rng = np.random.default_rng(6)
        bm = pd.Series(rng.normal(0.0, 0.02, 300), index=dates_300)
        returns = pd.DataFrame({'NEG': -bm.values, 'BIG': bm.values * 8.0}, index=dates_300)
        betas = estimate_betas(pd.Index(['NEG', 'BIG']), returns, bm)
        assert betas['NEG'] == 0.0
        assert betas['BIG'] == 5.0

    def test_no_benchmark_defaults_to_one(self, dates_300):
        returns = _iid_returns(['A', 'B'], dates_300)
        assert (estimate_betas(pd.Index(['A', 'B']), returns, None) == 1.0).all()

    def test_short_overlap_defaults_to_one(self, dates_300):
        returns = _iid_returns(['A', 'B'], dates_300)
        bm = pd.Series(np.random.default_rng(1).normal(0, 0.02, 30), index=dates_300[-30:])
        assert (estimate_betas(pd.Index(['A', 'B']), returns, bm) == 1.0).all()

    def test_ticker_missing_from_returns_defaults_to_one(self, dates_300):
        returns = _iid_returns(['A'], dates_300)
        bm = pd.Series(np.random.default_rng(1).normal(0, 0.02, 300), index=dates_300)
        betas = estimate_betas(pd.Index(['A', 'MISSING']), returns, bm)
        assert betas['MISSING'] == 1.0
        assert betas['A'] != 1.0

    def test_nan_rows_are_dropped_consistently(self, dates_300):
        rng = np.random.default_rng(8)
        bm = pd.Series(rng.normal(0.001, 0.02, 300), index=dates_300)
        returns = pd.DataFrame({'A': bm.values * 1.5 + rng.normal(0, 0.005, 300)}, index=dates_300)
        returns.iloc[-10, 0] = np.nan
        betas = estimate_betas(pd.Index(['A']), returns, bm)
        frame = pd.DataFrame({'A': returns['A'].iloc[-252:], 'bm': bm.iloc[-252:]}).dropna()
        assert betas['A'] == pytest.approx(float(frame['A'].cov(frame['bm']) / frame['bm'].var()), abs=1e-12)


class TestPositionLimits:
    def test_single_stock_cap(self, dates_300):
        weights = pd.Series({"A": 0.5, "B": 0.2, "C": 0.15, "D": 0.15})
        adjusted, limits = apply_position_limits(weights, _iid_returns(list(weights.index), dates_300), max_single_stock=0.25)
        assert adjusted.max() <= 0.25 + 1e-6
        assert adjusted.sum() == pytest.approx(1.0, abs=1e-9)
        assert limits['limits_breached'] == ["A capped from 50.0% to 25%"]
        assert limits['max_single_stock_pct'] == 25.0

    def test_multiple_stocks_over_limit(self, dates_300):
        weights = pd.Series({"A": 0.4, "B": 0.35, "C": 0.15, "D": 0.10})
        adjusted, limits = apply_position_limits(weights, _iid_returns(list(weights.index), dates_300), max_single_stock=0.25)
        assert (adjusted <= 0.25 + 1e-6).all()
        assert adjusted.sum() == pytest.approx(1.0, abs=1e-9)
        assert len(limits['limits_breached']) == 2

    def test_no_breach_stays_same(self, dates_300):
        weights = pd.Series({"A": 0.25, "B": 0.25, "C": 0.25, "D": 0.25})
        adjusted, limits = apply_position_limits(weights, _iid_returns(list(weights.index), dates_300), max_single_stock=0.25)
        pd.testing.assert_series_equal(adjusted, weights)
        assert limits['limits_breached'] == []
        assert limits['portfolio_beta'] == 1.0

    def test_beta_cap(self, dates_300):
        weights = pd.Series({"A": 0.3, "B": 0.3, "C": 0.2, "D": 0.2})
        rng = np.random.default_rng(42)
        bm = pd.Series(rng.normal(0.001, 0.02, 300), index=dates_300)
        returns = pd.DataFrame({
            "A": bm.values * 3.0 + rng.normal(0, 0.005, 300),
            "B": bm.values * 2.5 + rng.normal(0, 0.005, 300),
            "C": bm.values * 0.5 + rng.normal(0, 0.005, 300),
            "D": bm.values * 0.3 + rng.normal(0, 0.005, 300),
        }, index=dates_300)
        adjusted, limits = apply_position_limits(weights, returns, benchmark_returns=bm, max_single_stock=0.60, max_portfolio_beta=1.5)
        assert limits['portfolio_beta'] <= 1.5 + 0.01
        assert limits['portfolio_beta'] >= 1.4
        assert adjusted.sum() == pytest.approx(1.0, abs=1e-9)
        assert adjusted['A'] < weights['A']
        assert adjusted['D'] > weights['D']
        assert any(m.startswith("Portfolio beta scaled") for m in limits['limits_breached'])

    def test_beta_no_cap_needed(self, dates_300):
        weights = pd.Series({"A": 0.5, "B": 0.5})
        rng = np.random.default_rng(42)
        bm = pd.Series(rng.normal(0.001, 0.02, 300), index=dates_300)
        returns = pd.DataFrame({
            "A": bm.values * 0.5 + rng.normal(0, 0.005, 300),
            "B": bm.values * 0.8 + rng.normal(0, 0.005, 300),
        }, index=dates_300)
        adjusted, limits = apply_position_limits(weights, returns, benchmark_returns=bm, max_single_stock=0.60, max_portfolio_beta=1.5)
        assert limits['portfolio_beta'] < 1.5
        pd.testing.assert_series_equal(adjusted, weights)

    def test_all_betas_above_cap_uses_inverse_beta(self, dates_300):
        weights = pd.Series({"A": 0.5, "B": 0.5})
        rng = np.random.default_rng(9)
        bm = pd.Series(rng.normal(0.0, 0.02, 300), index=dates_300)
        returns = pd.DataFrame({"A": bm.values * 2.0, "B": bm.values * 3.0}, index=dates_300)
        adjusted, limits = apply_position_limits(weights, returns, benchmark_returns=bm, max_single_stock=0.60, max_portfolio_beta=1.5)
        assert adjusted['A'] == pytest.approx(0.6)
        assert adjusted['B'] == pytest.approx(0.4)
        assert limits['portfolio_beta'] == pytest.approx(2.4, abs=0.01)

    def test_risk_limits_structure_and_json(self, dates_300):
        returns = _iid_returns(["A", "B", "C"], dates_300)
        weights = pd.Series(1.0 / 3, index=returns.columns)
        _, limits = apply_position_limits(weights, returns)
        assert set(limits) == {'max_single_stock_pct', 'portfolio_beta', 'limits_breached'}
        parsed = json.loads(json.dumps(sanitize(limits)))
        assert parsed['portfolio_beta'] == 1.0

    def test_messages_have_no_em_dash(self, dates_300):
        weights = pd.Series({"A": 0.7, "B": 0.3})
        rng = np.random.default_rng(3)
        bm = pd.Series(rng.normal(0.0, 0.02, 300), index=dates_300)
        returns = pd.DataFrame({"A": bm.values * 3.0, "B": bm.values * 2.0}, index=dates_300)
        _, limits = apply_position_limits(weights, returns, benchmark_returns=bm)
        assert limits['limits_breached']
        assert all('\u2014' not in m for m in limits['limits_breached'])
