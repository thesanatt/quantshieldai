import dataclasses

import pytest

from quantshield import config
from quantshield.config import (
    DSR_TRIALS,
    EMERGENCY_TRIGGERS,
    INDIA,
    INDIA_REGIME_WEIGHTS,
    INDIA_SECTOR_MAP,
    INDIA_TICKERS,
    MARKETS,
    REGIME_WEIGHTS,
    TICKERS,
    US,
    US_SECTOR_MAP,
    MarketConfig,
)

SIGNALS = {'momentum', 'vol_adj_momentum', 'mean_reversion', 'trend', 'cross_asset'}
REGIMES = {'risk_on', 'risk_off', 'crisis'}


@pytest.mark.parametrize('weights', [REGIME_WEIGHTS, INDIA_REGIME_WEIGHTS])
def test_regime_rows_sum_to_one_with_exactly_five_signals(weights):
    assert set(weights) == REGIMES
    for regime, row in weights.items():
        assert set(row) == SIGNALS, regime
        assert abs(sum(row.values()) - 1.0) < 1e-6, regime
        assert all(v >= 0 for v in row.values())


def test_us_rows_keep_registered_proportions():
    risk_on = REGIME_WEIGHTS['risk_on']
    assert risk_on['momentum'] / risk_on['cross_asset'] == pytest.approx(3.5, rel=1e-4)
    assert risk_on['trend'] / risk_on['mean_reversion'] == pytest.approx(4.0, rel=1e-4)
    crisis = REGIME_WEIGHTS['crisis']
    assert crisis['mean_reversion'] == pytest.approx(0.25 / 0.80, rel=1e-4)


def test_universes_unchanged():
    assert TICKERS == ['AAPL', 'GOOGL', 'AMZN', 'NVDA', 'JNJ', 'KO', 'BRK-B', 'COST', 'MSFT']
    assert INDIA_TICKERS == [
        'RELIANCE.NS', 'TCS.NS', 'INFY.NS', 'HDFCBANK.NS', 'ICICIBANK.NS',
        'BHARTIARTL.NS', 'ITC.NS', 'HINDUNILVR.NS', 'LT.NS', 'SBIN.NS',
        'BAJFINANCE.NS', 'MARUTI.NS', 'HCLTECH.NS', 'SUNPHARMA.NS',
        'NTPC.NS', 'WIPRO.NS', 'ADANIENT.NS', 'KOTAKBANK.NS',
        'AXISBANK.NS', 'TITAN.NS',
    ]
    assert US.tickers == tuple(TICKERS)
    assert INDIA.tickers == tuple(INDIA_TICKERS)
    assert US.benchmark == 'VOO' and INDIA.benchmark == '^NSEI'
    assert US.macro_tickers == ('^VIX', '^TNX', 'GLD', 'UUP', 'USO')
    assert INDIA.macro_tickers == ('^INDIAVIX', '^NSEI', 'USDINR=X', 'CL=F')


def test_emergency_triggers_pinned():
    assert EMERGENCY_TRIGGERS == {
        'us_vix': 40,
        'india_vix': 30,
        'daily_drop_pct': 5,
        'regime_to_crisis': True,
    }
    assert config.MAX_DRAWDOWN_TOLERANCE_PCT == 50


def test_dsr_trials_defined_and_shared():
    assert DSR_TRIALS == 37
    assert US.dsr_trials == INDIA.dsr_trials == DSR_TRIALS


def test_markets_registry_and_frozen():
    assert set(MARKETS) == {'us', 'india'}
    assert MARKETS['us'] is US and MARKETS['india'] is INDIA
    assert dataclasses.is_dataclass(MarketConfig)
    with pytest.raises(dataclasses.FrozenInstanceError):
        US.min_weight = 0.0


@pytest.mark.parametrize('cfg', [US, INDIA])
def test_limits_are_consistent(cfg):
    assert 0 < cfg.min_weight < cfg.max_weight <= 1
    assert cfg.max_single_stock <= cfg.max_weight
    assert cfg.max_single_stock <= cfg.max_sector_pct <= 1
    assert cfg.min_weight * len(cfg.tickers) < 1.0
    assert cfg.max_single_stock * len(cfg.tickers) > 1.0
    assert 0 < cfg.cvar_confidence < 1
    assert cfg.max_monthly_cvar > 0
    assert 0 <= cfg.tilt_strength <= 1
    assert cfg.vix_ticker in cfg.macro_tickers
    assert cfg.regime_weights is (REGIME_WEIGHTS if cfg.market == 'us' else INDIA_REGIME_WEIGHTS)


@pytest.mark.parametrize('cfg', [US, INDIA])
def test_sector_map_partitions_universe(cfg):
    seen: list[str] = []
    for members in cfg.sector_map.values():
        seen.extend(members)
    assert sorted(seen) == sorted(cfg.tickers)
    assert cfg.sector_map is (US_SECTOR_MAP if cfg.market == 'us' else INDIA_SECTOR_MAP)


def test_market_specific_values():
    assert US.currency == 'USD' and INDIA.currency == 'INR'
    assert US.notional_capital == 100000.0 and INDIA.notional_capital == 1000000.0
    assert US.transaction_cost == 0.0010
    assert INDIA.transaction_cost is None
    assert US.risk_free_annual is None
    assert INDIA.risk_free_annual == 0.065
    assert US.max_sector_pct == 0.40 and INDIA.max_sector_pct == 0.30
    assert US.max_single_stock == 0.25 and INDIA.max_single_stock == 0.15
    assert US.benchmark_label == 'S&P 500' and INDIA.benchmark_label == 'Nifty 50'


def test_deleted_constants_are_gone():
    for name in ('VOL_TARGET_US', 'VOL_TARGET_INDIA', 'VOL_SCALAR_MIN', 'VOL_SCALAR_MAX',
                 'FINNHUB_API_KEY', 'ALPHA_VANTAGE_API_KEY'):
        assert not hasattr(config, name), name
    for weights in (REGIME_WEIGHTS, INDIA_REGIME_WEIGHTS):
        for row in weights.values():
            assert not {'earnings', 'vix_term_structure', 'copper_gold'} & set(row)
