from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest
import scipy.cluster.hierarchy as sch

from quantshield.risk.hrp import hrp_weights
from tests.conftest import make_dates, make_returns


@pytest.fixture
def two_uncorrelated() -> pd.DataFrame:
    a = np.tile([1.0, -1.0, 1.0, -1.0], 50)
    b = np.tile([1.0, 1.0, -1.0, -1.0], 50) * 2.0
    return pd.DataFrame({'A': a, 'B': b})


class TestHRP:
    def test_two_uncorrelated_assets_get_inverse_variance_weights(self, two_uncorrelated):
        assert two_uncorrelated.corr().loc['A', 'B'] == pytest.approx(0.0, abs=1e-12)
        assert two_uncorrelated['B'].var() / two_uncorrelated['A'].var() == pytest.approx(4.0)
        weights = hrp_weights(two_uncorrelated)
        assert weights['A'] == pytest.approx(0.8, abs=1e-12)
        assert weights['B'] == pytest.approx(0.2, abs=1e-12)

    def test_order_of_columns_does_not_matter(self, two_uncorrelated):
        weights = hrp_weights(two_uncorrelated[['B', 'A']])
        assert weights['A'] == pytest.approx(0.8, abs=1e-12)
        assert weights['B'] == pytest.approx(0.2, abs=1e-12)

    def test_many_assets_sum_to_one_and_non_negative(self):
        rng = np.random.default_rng(42)
        returns = pd.DataFrame({t: rng.normal(0.0005, rng.uniform(0.01, 0.04), 400) for t in "ABCDEFGH"}, index=make_dates(400))
        weights = hrp_weights(returns)
        assert weights.sum() == pytest.approx(1.0, abs=1e-12)
        assert (weights >= 0).all()
        assert set(weights.index) == set(returns.columns)

    def test_lower_variance_gets_more_weight(self):
        rng = np.random.default_rng(0)
        returns = pd.DataFrame({
            'CALM': rng.normal(0, 0.005, 500),
            'WILD': rng.normal(0, 0.05, 500),
            'MID': rng.normal(0, 0.02, 500),
        }, index=make_dates(500))
        weights = hrp_weights(returns)
        assert weights['CALM'] > weights['MID'] > weights['WILD']

    def test_zero_variance_asset_does_not_break(self):
        returns = make_returns(200, ('A', 'B'), seed=1, mean=0.0, vol=0.02)
        returns.insert(0, 'FLAT', 0.0)
        weights = hrp_weights(returns)
        assert np.isfinite(weights.values).all()
        assert weights.sum() == pytest.approx(1.0, abs=1e-9)
        assert weights['FLAT'] > weights['A'] and weights['FLAT'] > weights['B']

    def test_three_identical_assets_bisect_half_then_quarter(self, returns_perfect_corr: pd.DataFrame) -> None:
        weights = hrp_weights(returns_perfect_corr)
        assert weights.sum() == pytest.approx(1.0, abs=1e-12)
        assert sorted(weights.tolist()) == pytest.approx([0.25, 0.25, 0.5], abs=1e-12)

    def test_columns_of_input_are_preserved_in_output(self) -> None:
        returns = make_returns(120, ('Z', 'M', 'A'), seed=3)
        weights = hrp_weights(returns)
        assert set(weights.index) == {'Z', 'M', 'A'}
        assert len(weights) == 3

    def test_uses_ward_linkage(self, two_uncorrelated):
        calls: list[str] = []

        def spy(*args: object, **kwargs: object) -> np.ndarray:
            calls.append(kwargs.get('method', args[1] if len(args) > 1 else ''))
            return sch.linkage(*args, **kwargs)

        with patch('quantshield.risk.hrp.linkage', side_effect=spy):
            hrp_weights(two_uncorrelated)
        assert calls == ['ward']
