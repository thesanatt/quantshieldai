import numpy as np
import pandas as pd
import pytest

from quantshield.risk.cvar import apply_cvar_constraint, compute_portfolio_cvar
from tests.conftest import make_dates, make_returns

TICKERS = ("AAPL", "GOOGL", "MSFT", "AMZN")


@pytest.fixture
def portfolio_returns_df() -> pd.DataFrame:
    return make_returns(500, TICKERS, seed=42, mean=0.0004, vol=0.02)


@pytest.fixture
def equal_weights() -> pd.Series:
    return pd.Series(0.25, index=list(TICKERS))


def _monthly_cvar(weights: pd.Series, returns: pd.DataFrame, confidence: float = 0.95) -> float:
    monthly = (1 + returns[weights.index]).resample('ME').prod() - 1
    port = (monthly * weights).sum(axis=1)
    var_val = np.percentile(port, (1 - confidence) * 100)
    return float(port[port <= var_val].mean())


class TestComputePortfolioCVaR:
    def test_known_sample_matches_hand_computation(self):
        values = np.round(np.arange(-0.50, 0.50, 0.01), 2)
        returns = pd.DataFrame({'A': values}, index=make_dates(100))
        result = compute_portfolio_cvar(pd.Series({'A': 1.0}), returns, confidence=0.95)
        assert result['var'] == pytest.approx(-0.4505, abs=1e-9)
        assert result['portfolio_cvar'] == pytest.approx(-0.48, abs=1e-9)
        assert result['component_cvar'] == {'A': pytest.approx(-0.48, abs=1e-9)}
        assert result['confidence'] == 0.95

    def test_two_asset_components_sum_to_portfolio(self):
        rng = np.random.default_rng(1)
        returns = pd.DataFrame({'A': rng.normal(0, 0.02, 400), 'B': rng.normal(0, 0.01, 400)}, index=make_dates(400))
        weights = pd.Series({'A': 0.3, 'B': 0.7})
        result = compute_portfolio_cvar(weights, returns)
        tail = (returns * weights).sum(axis=1)
        tail = tail[tail <= np.percentile(tail, 5)]
        assert result['portfolio_cvar'] == pytest.approx(float(tail.mean()), abs=1e-7)
        assert sum(result['component_cvar'].values()) == pytest.approx(result['portfolio_cvar'], abs=1e-6)
        assert result['component_cvar']['A'] == pytest.approx(float((returns.loc[tail.index, 'A'] * 0.3).mean()), abs=1e-7)

    def test_structure(self, equal_weights, portfolio_returns_df):
        result = compute_portfolio_cvar(equal_weights, portfolio_returns_df)
        assert set(result) == {'portfolio_cvar', 'var', 'component_cvar', 'confidence'}
        assert len(result['component_cvar']) == 4
        assert result['portfolio_cvar'] <= result['var']
        assert all(isinstance(v, float) for v in result['component_cvar'].values())

    def test_confidence_is_echoed(self, equal_weights, portfolio_returns_df):
        assert compute_portfolio_cvar(equal_weights, portfolio_returns_df, confidence=0.99)['confidence'] == 0.99

    def test_insufficient_data(self, equal_weights):
        short = pd.DataFrame({t: [0.01, -0.02, 0.0] for t in equal_weights.index})
        result = compute_portfolio_cvar(equal_weights, short)
        assert result == {'portfolio_cvar': 0.0, 'var': 0.0, 'component_cvar': {}, 'confidence': 0.95}


class TestApplyCVaRConstraint:
    @pytest.fixture
    def violating(self) -> tuple[pd.Series, pd.DataFrame]:
        rng = np.random.default_rng(7)
        returns = pd.DataFrame({
            'HI': rng.normal(-0.001, 0.03, 800),
            'LO': rng.normal(0.0005, 0.004, 800),
        }, index=make_dates(800))
        return pd.Series({'HI': 0.5, 'LO': 0.5}), returns

    def test_reduces_cvar_on_violating_portfolio(self, violating):
        weights, returns = violating
        before = _monthly_cvar(weights, returns)
        adjusted = apply_cvar_constraint(weights, returns, max_monthly_cvar=0.01, confidence=0.95)
        after = _monthly_cvar(adjusted, returns)
        assert abs(before) > 0.01
        assert abs(after) < abs(before)
        assert adjusted['HI'] < weights['HI']
        assert adjusted.sum() == pytest.approx(1.0, abs=1e-9)
        assert (adjusted >= 0).all()

    def test_no_change_if_compliant(self, equal_weights, portfolio_returns_df):
        adjusted = apply_cvar_constraint(equal_weights, portfolio_returns_df, max_monthly_cvar=1.0)
        pd.testing.assert_series_equal(adjusted, equal_weights)

    def test_preserves_sum_and_sign(self, equal_weights, portfolio_returns_df):
        adjusted = apply_cvar_constraint(equal_weights, portfolio_returns_df, max_monthly_cvar=0.001)
        assert adjusted.sum() == pytest.approx(1.0, abs=1e-9)
        assert (adjusted >= 0).all()
        assert list(adjusted.index) == list(equal_weights.index)

    def test_too_few_months_returns_input(self, equal_weights):
        returns = pd.DataFrame({t: np.full(40, -0.05) for t in equal_weights.index}, index=make_dates(40))
        pd.testing.assert_series_equal(apply_cvar_constraint(equal_weights, returns, max_monthly_cvar=0.0), equal_weights)
