import numpy as np
import pandas as pd
import pytest

from quantshield.risk.correlation import correlation_monitor
from tests.conftest import make_dates, make_returns


class TestCorrelationMonitor:
    def test_single_asset_returns_empty_list(self):
        assert correlation_monitor(make_returns(60, ("ONLY",), seed=0), window=30) == (0.0, [])

    def test_perfectly_correlated_pair(self):
        base = np.random.default_rng(1).normal(0, 0.02, 60)
        returns = pd.DataFrame({"A": base, "B": base * 2.0}, index=make_dates(60))
        avg, pairs = correlation_monitor(returns, window=30)
        assert avg == pytest.approx(1.0)
        assert pairs == [{'pair': 'A/B', 'corr': 1.0}]

    def test_average_matches_pandas_upper_triangle(self):
        returns = make_returns(100, tuple("ABCD"), seed=2, mean=0.0)
        avg, pairs = correlation_monitor(returns, window=30)
        corr = returns.iloc[-30:].corr().values
        expected = corr[np.triu_indices(4, k=1)].mean()
        assert avg == pytest.approx(round(float(expected), 3))
        assert len(pairs) == 5
        strengths = [abs(p['corr']) for p in pairs]
        assert strengths == sorted(strengths, reverse=True)

    def test_at_most_five_pairs(self):
        returns = make_returns(100, tuple("ABCDEFGH"), seed=3, mean=0.0)
        _, pairs = correlation_monitor(returns)
        assert len(pairs) == 5
        assert all(set(p) == {'pair', 'corr'} for p in pairs)
