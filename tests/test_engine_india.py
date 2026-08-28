import numpy as np
import pandas as pd
import pytest

from quantshield.config import INDIA, INDIA_REGIME_WEIGHTS, INDIA_SECTOR_MAP, INDIA_TICKERS, MarketConfig
from quantshield.research.backtest import walk_forward_backtest
from quantshield.research.portfolio import build_weights, enforce_limits, within_limits
from quantshield.signals.cross_asset import india_cross_asset_signals
from quantshield.signals.regime import india_detect_regime
from tests.conftest import make_dates, make_prices
from tests.test_engine_cli import synthetic_panel


@pytest.fixture(scope='module')
def panel():
    return synthetic_panel(INDIA)


@pytest.fixture
def india_dates() -> pd.DatetimeIndex:
    return make_dates(500)


class TestIndiaRegimeDetection:
    def test_low_india_vix_risk_on(self, india_dates):
        macro = pd.DataFrame({
            '^INDIAVIX': np.full(len(india_dates), 12.0),
            '^NSEI': np.linspace(18000, 22000, len(india_dates)),
            'USDINR=X': np.full(len(india_dates), 83.5),
            'CL=F': np.full(len(india_dates), 75.0),
        }, index=india_dates)
        regime, _, _ = india_detect_regime(macro)
        assert regime == 'risk_on'

    def test_high_india_vix_not_risk_on(self, india_dates):
        macro = pd.DataFrame({
            '^INDIAVIX': np.full(len(india_dates), 30.0),
            '^NSEI': np.linspace(22000, 18000, len(india_dates)),
            'USDINR=X': np.linspace(83, 88, len(india_dates)),
            'CL=F': np.linspace(70, 90, len(india_dates)),
        }, index=india_dates)
        regime, _, _ = india_detect_regime(macro)
        assert regime in ('crisis', 'risk_off')

    def test_oil_above_90_blocks_risk_on(self, india_dates):
        macro = pd.DataFrame({
            '^INDIAVIX': np.full(len(india_dates), 12.0),
            '^NSEI': np.linspace(18000, 22000, len(india_dates)),
            'USDINR=X': np.full(len(india_dates), 83.5),
            'CL=F': np.full(len(india_dates), 95.0),
        }, index=india_dates)
        regime, _, details = india_detect_regime(macro)
        assert regime != 'risk_on'
        assert 'oil_override' in details

    def test_regime_result_structure(self, panel):
        _, _, macro_close, _ = panel
        regime, confidence, details = india_detect_regime(macro_close)
        assert regime in ('risk_on', 'risk_off', 'crisis')
        assert 0 <= confidence <= 1
        assert details['vix_current'] > 0
        assert set(details['regime_scores']) == {'risk_on', 'risk_off', 'crisis'}


class TestIndiaCrossAssetSignals:
    def test_rupee_depreciation_favours_it_exporters(self, india_dates):
        prices = make_prices(len(india_dates), ('TCS.NS', 'INFY.NS', 'HINDUNILVR.NS', 'ITC.NS'), seed=42)
        returns = prices.pct_change().dropna()
        macro = pd.DataFrame({
            'USDINR=X': np.concatenate([np.full(len(india_dates) - 21, 83.0), np.linspace(83, 88, 21)]),
            'CL=F': np.full(len(india_dates), 75.0),
            '^NSEI': np.full(len(india_dates), 20000.0),
        }, index=india_dates)
        signals, _ = india_cross_asset_signals(prices, macro, returns, sector_map=INDIA_SECTOR_MAP)
        assert signals['TCS.NS'] > signals['HINDUNILVR.NS']

    def test_oil_spike_hurts_consumer_names(self, india_dates):
        prices = make_prices(len(india_dates), ('RELIANCE.NS', 'HINDUNILVR.NS', 'TCS.NS'), seed=42)
        returns = prices.pct_change().dropna()
        macro = pd.DataFrame({
            'CL=F': np.concatenate([np.full(len(india_dates) - 21, 70.0), np.linspace(70, 85, 21)]),
            'USDINR=X': np.full(len(india_dates), 83.5),
            '^NSEI': np.full(len(india_dates), 20000.0),
        }, index=india_dates)
        signals, _ = india_cross_asset_signals(prices, macro, returns, sector_map=INDIA_SECTOR_MAP)
        assert signals['HINDUNILVR.NS'] <= 0
        assert signals['HINDUNILVR.NS'] <= signals['TCS.NS']

    def test_signals_bounded(self, panel):
        close, returns, macro_close, bench = panel
        signals, betas = india_cross_asset_signals(close, macro_close, returns, benchmark_returns=bench, sector_map=INDIA_SECTOR_MAP)
        assert signals.between(-1, 1).all()
        assert len(betas) == len(close.columns)


class TestIndiaBuildWeights:
    @pytest.mark.parametrize('regime', ['risk_on', 'risk_off', 'crisis'])
    def test_weights_feasible_for_every_regime(self, panel, regime):
        close, returns, macro_close, bench = panel
        weights, details = build_weights(close, returns, macro_close, bench, INDIA, regime)
        assert list(weights.index) == list(close.columns)
        assert weights.sum() == pytest.approx(1.0, abs=1e-9)
        assert within_limits(weights, INDIA)
        assert details['signal_weights'] == INDIA_REGIME_WEIGHTS[regime]
        assert set(details['signals']) == {'momentum', 'vol_adj_momentum', 'mean_reversion', 'trend', 'cross_asset'}
        assert details['hrp'].sum() == pytest.approx(1.0, abs=1e-9)
        for members in INDIA_SECTOR_MAP.values():
            assert weights.reindex(members).sum() <= INDIA.max_sector_pct + 1e-6

    def test_weights_invariant_to_regime_row_scale(self, panel):
        close, returns, macro_close, bench = panel
        scaled = {r: {k: v * 0.8 for k, v in row.items()} for r, row in INDIA.regime_weights.items()}
        cfg_scaled = MarketConfig(**{**INDIA.__dict__, 'regime_weights': scaled})
        base, _ = build_weights(close, returns, macro_close, bench, INDIA, 'risk_off')
        other, _ = build_weights(close, returns, macro_close, bench, cfg_scaled, 'risk_off')
        pd.testing.assert_series_equal(base, other)

    def test_unknown_regime_raises(self, panel):
        close, returns, macro_close, bench = panel
        with pytest.raises(KeyError):
            build_weights(close, returns, macro_close, bench, INDIA, 'unknown')

    def test_enforce_limits_fixes_concentrated_input(self, panel):
        close, returns, _, bench = panel
        raw = pd.Series(0.0, index=close.columns)
        raw[INDIA_SECTOR_MAP['banks']] = 0.15
        raw['RELIANCE.NS'] = 0.25
        raw = raw / raw.sum()
        fixed, limits = enforce_limits(raw, returns, bench, INDIA)
        assert within_limits(fixed, INDIA)
        assert fixed.sum() == pytest.approx(1.0, abs=1e-9)
        assert limits['portfolio_beta'] <= INDIA.max_portfolio_beta + 1e-6


class TestIndiaWalkForward:
    def test_uses_cnc_delivery_schedule(self, panel):
        close, returns, macro_close, bench = panel
        res = walk_forward_backtest(close, returns, macro_close, bench, INDIA, india_detect_regime)
        assert res is not None
        assert 'CNC' in res['cost_model']
        assert 'bench_return' in res and 'voo_return' not in res
        assert res['port_maxdd'] <= 0 and res['bench_maxdd'] <= 0
        assert res['total_periods'] == (len(returns) - 252) // 21
        assert res['fallback_periods'] == 0

    def test_india_rf_is_6_5_percent(self, panel):
        close, returns, macro_close, bench = panel
        from quantshield.research.backtest import _daily_rf, _perf_stats
        res = walk_forward_backtest(close, returns, macro_close, bench, INDIA, india_detect_regime)
        values = np.concatenate(([1.0], np.cumprod(1 + res['daily_returns'].values)))
        assert _perf_stats(values, _daily_rf(macro_close, 0.065))['sharpe'] == res['port_sharpe']


def test_all_india_tickers_have_a_sector():
    covered = {t for members in INDIA_SECTOR_MAP.values() for t in members}
    assert covered == set(INDIA_TICKERS)
