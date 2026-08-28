import numpy as np
import pandas as pd
import pytest

from quantshield.utils import rank_normalize


def test_output_range_and_endpoints():
    result = rank_normalize(pd.Series([10, 20, 30, 40, 50]))
    assert result.tolist() == pytest.approx([-0.6, -0.2, 0.2, 0.6, 1.0])


def test_outlier_insensitive():
    normal = rank_normalize(pd.Series([1, 2, 3, 4, 5]))
    outlier = rank_normalize(pd.Series([1, 2, 3, 4, 5000]))
    pd.testing.assert_series_equal(normal, outlier)


def test_constant_series_returns_zero():
    result = rank_normalize(pd.Series([5, 5, 5]))
    assert result.tolist() == [0.0, 0.0, 0.0]
    assert result.dtype == float


def test_two_values():
    assert rank_normalize(pd.Series([1, 2])).tolist() == [0.0, 1.0]


def test_ties_share_the_average_rank():
    assert rank_normalize(pd.Series([1, 2, 2, 3])).tolist() == pytest.approx([-0.5, 0.25, 0.25, 1.0])
    assert rank_normalize(pd.Series([5, 5, 1])).tolist() == pytest.approx([2 / 3, 2 / 3, -1 / 3])


def test_preserves_index():
    result = rank_normalize(pd.Series([3, 1, 2], index=['A', 'B', 'C']))
    assert list(result.index) == ['A', 'B', 'C']
    assert result.tolist() == pytest.approx([1.0, -1 / 3, 1 / 3])


def test_nan_stays_nan_and_others_rank_among_themselves():
    result = rank_normalize(pd.Series([1, 2, np.nan, 4]))
    assert np.isnan(result.iloc[2])
    assert result.drop(index=2).tolist() == pytest.approx([-1 / 3, 1 / 3, 1.0])
