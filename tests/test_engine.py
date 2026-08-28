import numpy as np
import pandas as pd
import pytest
from hypothesis import assume, given, settings
from hypothesis import strategies as st
from hypothesis.extra.numpy import arrays

from quantshield.config import REGIME_WEIGHTS, US, US_SECTOR_MAP
from quantshield.research.portfolio import build_weights, within_limits
from quantshield.risk.hrp import hrp_weights
from quantshield.signals.composite import SIGNAL_KEYS, composite_score, compute_signals
from quantshield.signals.mean_reversion import rsi_signal
from quantshield.signals.momentum import momentum_signal, vol_adj_momentum
from quantshield.signals.regime import us_detect_regime
from quantshield.signals.trend import trend_signal
from quantshield.utils import rank_normalize
from tests.conftest import make_dates


class TestMomentumSignal:
    def test_single_ticker_ranks_to_zero(self, prices_single_ticker: pd.DataFrame) -> None:
        result = momentum_signal(prices_single_ticker, lookback=252, skip=21)
        assert list(result.index) == ['SOLO']
        assert result['SOLO'] != 0.0
        assert (rank_normalize(result) == 0.0).all()

    def test_hand_computed(self) -> None:
        dates = make_dates(300)
        prices_a = np.concatenate([np.full(278, 100.0), [120.0], np.full(21, 120.0)])
        prices_b = np.concatenate([np.full(278, 100.0), [80.0], np.full(21, 80.0)])
        result = momentum_signal(pd.DataFrame({'A': prices_a, 'B': prices_b}, index=dates), lookback=252, skip=21)
        assert result['A'] == pytest.approx(0.2)
        assert result['B'] == pytest.approx(-0.2)

    def test_skip_month_is_excluded(self) -> None:
        prices = np.full(300, 100.0)
        prices[-21:] = 500.0
        assert momentum_signal(pd.DataFrame({'A': prices}, index=make_dates(300)), lookback=252, skip=21)['A'] == 0.0


class TestRsiSignal:
    def test_flat_prices_saturate_positive(self, prices_flat: pd.DataFrame) -> None:
        result = rsi_signal(prices_flat)
        assert result.notna().all()
        assert (result == 0.0).all()


class TestVolAdjMomentum:
    def test_higher_vol_lowers_score_for_same_return(self) -> None:
        rng = np.random.default_rng(8)
        calm = rng.normal(0, 0.005, 300)
        wild = rng.normal(0, 0.03, 300)
        calm = calm - calm.mean() + 0.0005
        wild = wild - wild.mean() + 0.0005
        returns = pd.DataFrame({'CALM': calm, 'WILD': wild, 'MID': rng.normal(0.0005, 0.015, 300)}, index=make_dates(300))
        result = vol_adj_momentum(returns)
        assert result['CALM'] > result['WILD']


class TestBuildWeightsUS:
    @pytest.mark.parametrize('regime', ['risk_on', 'risk_off', 'crisis'])
    def test_weights_feasible_for_every_regime(
        self, prices: pd.DataFrame, returns: pd.DataFrame, macro_close: pd.DataFrame,
        benchmark_returns: pd.Series, regime: str,
    ) -> None:
        weights, details = build_weights(prices, returns, macro_close, benchmark_returns, US, regime)
        assert list(weights.index) == list(prices.columns)
        assert weights.sum() == pytest.approx(1.0, abs=1e-9)
        assert within_limits(weights, US)
        assert details['signal_weights'] == REGIME_WEIGHTS[regime]
        assert list(details['signals']) == SIGNAL_KEYS
        assert details['hrp'].sum() == pytest.approx(1.0, abs=1e-9)
        for members in US_SECTOR_MAP.values():
            assert weights.reindex(members).sum() <= US.max_sector_pct + 1e-6

    def test_composite_matches_explicit_weighted_sum(
        self, prices: pd.DataFrame, returns: pd.DataFrame, macro_close: pd.DataFrame, benchmark_returns: pd.Series,
    ) -> None:
        regime, _, _ = us_detect_regime(macro_close)
        signals, _ = compute_signals(prices, macro_close, returns, benchmark_returns, 'us', regime, US_SECTOR_MAP)
        weights = REGIME_WEIGHTS[regime]
        explicit = sum(weights[k] * signals[k] for k in SIGNAL_KEYS)
        assert np.allclose(composite_score(signals, weights).to_numpy(), explicit.to_numpy())

    def test_signals_are_rank_normalized(
        self, prices: pd.DataFrame, returns: pd.DataFrame, macro_close: pd.DataFrame, benchmark_returns: pd.Series,
    ) -> None:
        signals, _ = compute_signals(prices, macro_close, returns, benchmark_returns, 'us', 'risk_on', None)
        n = len(prices.columns)
        expected = {round(2 * (k + 1) / n - 1, 12) for k in range(n)}
        for key in ('momentum', 'vol_adj_momentum', 'mean_reversion'):
            assert set(signals[key].round(12)) <= expected | {0.0}, key


class TestStress:
    def test_one_day_of_data(self) -> None:
        prices = pd.DataFrame({'A': [100.0], 'B': [200.0]}, index=make_dates(1))
        assert (momentum_signal(prices, lookback=252, skip=21) == 0.0).all()
        assert (trend_signal(prices) == 0.0).all()

    def test_ten_days_of_data(self) -> None:
        rng = np.random.default_rng(33)
        prices = pd.DataFrame({'A': rng.uniform(90, 110, 10), 'B': rng.uniform(90, 110, 10)}, index=make_dates(10))
        assert momentum_signal(prices).notna().all()
        assert (rsi_signal(prices) == 0.0).all()

    def test_zero_returns(self, returns_zero: pd.DataFrame) -> None:
        prices = pd.DataFrame({col: np.full(300, 100.0) for col in returns_zero.columns}, index=returns_zero.index)
        assert momentum_signal(prices).notna().all()
        assert rsi_signal(prices).notna().all()
        assert vol_adj_momentum(returns_zero).notna().all()
        assert (rank_normalize(momentum_signal(prices)) == 0.0).all()


class TestPropertyBased:
    @given(
        data=arrays(
            dtype=np.float64,
            shape=st.tuples(st.integers(min_value=280, max_value=400), st.integers(min_value=2, max_value=5)),
            elements=st.floats(min_value=0.01, max_value=1000.0, allow_nan=False, allow_infinity=False),
        )
    )
    @settings(max_examples=20, deadline=10000)
    def test_signal_range_property(self, data: np.ndarray) -> None:
        assume(np.all(np.std(data, axis=0) > 1e-10))
        dates = pd.bdate_range(start='2024-01-02', periods=data.shape[0])
        cols = [f'T{i}' for i in range(data.shape[1])]
        prices = pd.DataFrame(data, index=dates, columns=cols)
        mom = momentum_signal(prices, lookback=252, skip=21)
        assert np.all(np.isfinite(mom.to_numpy()))
        assert (mom >= -1.0).all()
        for signal in [rank_normalize(mom), rsi_signal(prices), trend_signal(prices)]:
            for v in signal.values:
                assert np.isnan(v) or -1 <= v <= 1

    @given(
        data=arrays(
            dtype=np.float64,
            shape=st.tuples(st.integers(min_value=100, max_value=400), st.integers(min_value=2, max_value=5)),
            elements=st.floats(min_value=-0.05, max_value=0.05, allow_nan=False, allow_infinity=False),
        )
    )
    @settings(max_examples=20, deadline=10000)
    def test_hrp_weights_property(self, data: np.ndarray) -> None:
        assume(np.all(np.std(data, axis=0) > 1e-8))
        assume(not np.all(data == 0))
        dates = pd.bdate_range(start='2024-01-02', periods=data.shape[0])
        cols = [f'T{i}' for i in range(data.shape[1])]
        returns = pd.DataFrame(data, index=dates, columns=cols)
        cov = returns.cov()
        assume(np.all(np.diag(cov.values) > 1e-12))
        corr = returns.corr()
        assume(not np.any(np.isnan(corr.values)))
        w = hrp_weights(returns)
        assert abs(w.sum() - 1.0) < 1e-4
        assert all(v >= -1e-6 for v in w.values)
