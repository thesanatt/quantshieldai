from collections.abc import Callable, Iterator

import numpy as np
import pandas as pd
import pytest

import quantshield.signals.fama_french as ff
from quantshield.signals.fama_french import decompose_returns


@pytest.fixture
def monthly_returns() -> pd.Series:
    rng = np.random.default_rng(42)
    dates = pd.date_range(start="2022-01-31", periods=36, freq="ME")
    return pd.Series(rng.normal(0.008, 0.04, len(dates)), index=dates)


@pytest.fixture(autouse=True)
def clear_cache() -> Iterator[None]:
    ff._FF_CACHE.clear()
    yield
    ff._FF_CACHE.clear()


def _fake_factors(months: pd.DatetimeIndex) -> pd.DataFrame:
    rng = np.random.default_rng(7)
    n = len(months)
    return pd.DataFrame({
        'Mkt-RF': rng.normal(0.007, 0.045, n),
        'SMB': rng.normal(0.002, 0.03, n),
        'HML': rng.normal(0.003, 0.03, n),
        'RMW': rng.normal(0.003, 0.02, n),
        'CMA': rng.normal(0.003, 0.02, n),
        'RF': np.full(n, 0.004),
        'Mom': rng.normal(0.006, 0.04, n),
    }, index=months)


def _month_starts(series: pd.Series) -> pd.DatetimeIndex:
    return pd.DatetimeIndex(series.index).to_period('M').to_timestamp()


def _loader(factors: pd.DataFrame) -> Callable[[str], pd.DataFrame]:
    def load(file_name: str) -> pd.DataFrame:
        if file_name == ff.MOM_FILE:
            return factors[['Mom']]
        return factors.drop(columns=['Mom'])
    return load


class TestDecomposeReturns:
    def test_insufficient_data(self):
        short = pd.Series([0.01, 0.02], index=pd.date_range("2024-01-31", periods=2, freq="ME"))
        result = decompose_returns(short)
        assert result['error'] == 'insufficient_data'
        assert result['n_months'] == 2

    def test_download_failure_returns_error_not_synthetic(self, monkeypatch, monthly_returns):
        def fail(file_name: str) -> pd.DataFrame:
            raise ConnectionError("offline")

        monkeypatch.setattr(ff, '_download_monthly', fail)
        result = decompose_returns(monthly_returns)
        assert result['error'] == 'factor_data_unavailable'
        assert 'alpha' not in result
        assert 'is_synthetic' not in result

    def test_short_factor_window_returns_error(self, monkeypatch, monthly_returns):
        months = _month_starts(monthly_returns)[:6]
        monkeypatch.setattr(ff, '_download_monthly', _loader(_fake_factors(months)))
        assert decompose_returns(monthly_returns)['error'] == 'factor_data_unavailable'

    def test_real_factors_decompose(self, monkeypatch, monthly_returns):
        months = _month_starts(monthly_returns)
        monkeypatch.setattr(ff, '_download_monthly', _loader(_fake_factors(months)))
        result = decompose_returns(monthly_returns)
        assert 'error' not in result
        assert result['n_months'] == 36
        assert 0.0 <= result['r_squared'] <= 1.0
        assert set(result['factor_betas']) == set(ff.FACTOR_COLS)
        for info in result['factor_betas'].values():
            assert set(info) == {'beta', 'tstat', 'pvalue'}
            assert 0.0 <= info['pvalue'] <= 1.0
        assert result['residual_alpha_annualized'] == pytest.approx(result['alpha'] * 12.0, abs=1e-3)

    def test_known_factor_loadings_are_recovered(self, monkeypatch):
        months = pd.date_range("2015-01-01", periods=120, freq="MS")
        factors = _fake_factors(months)
        monkeypatch.setattr(ff, '_download_monthly', _loader(factors))
        port = 0.002 + factors['RF'] + 1.2 * factors['Mkt-RF'] - 0.5 * factors['HML'] + 0.3 * factors['Mom']
        result = decompose_returns(port)
        assert result['factor_betas']['Mkt-RF']['beta'] == pytest.approx(1.2, abs=1e-6)
        assert result['factor_betas']['HML']['beta'] == pytest.approx(-0.5, abs=1e-6)
        assert result['factor_betas']['Mom']['beta'] == pytest.approx(0.3, abs=1e-6)
        assert result['factor_betas']['SMB']['beta'] == pytest.approx(0.0, abs=1e-6)
        assert result['alpha'] == pytest.approx(0.002, abs=1e-6)
        assert result['r_squared'] == pytest.approx(1.0, abs=1e-6)
