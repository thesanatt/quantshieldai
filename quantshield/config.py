from dataclasses import dataclass

TICKERS = ['AAPL', 'GOOGL', 'AMZN', 'NVDA', 'JNJ', 'KO', 'BRK-B', 'COST', 'MSFT']

BENCHMARK_TICKER = 'VOO'

MACRO_TICKERS = ['^VIX', '^TNX', 'GLD', 'UUP', 'USO']

TOTAL_CAPITAL = 100000

TILT_STRENGTH = 0.5
MIN_WEIGHT = 0.02
MAX_WEIGHT = 0.40


def _normalized(rows: dict[str, dict[str, float]]) -> dict[str, dict[str, float]]:
    return {
        regime: {k: round(v / sum(w.values()), 6) for k, v in w.items()}
        for regime, w in rows.items()
    }


REGIME_WEIGHTS = _normalized({
    'risk_on': {
        'momentum': 0.35, 'vol_adj_momentum': 0.25,
        'mean_reversion': 0.05, 'trend': 0.20, 'cross_asset': 0.10,
    },
    'risk_off': {
        'momentum': 0.20, 'vol_adj_momentum': 0.20,
        'mean_reversion': 0.15, 'trend': 0.20, 'cross_asset': 0.15,
    },
    'crisis': {
        'momentum': 0.10, 'vol_adj_momentum': 0.10,
        'mean_reversion': 0.25, 'trend': 0.15, 'cross_asset': 0.20,
    },
})

INDIA_TICKERS = ['RELIANCE.NS', 'TCS.NS', 'INFY.NS', 'HDFCBANK.NS', 'ICICIBANK.NS',
                 'BHARTIARTL.NS', 'ITC.NS', 'HINDUNILVR.NS', 'LT.NS', 'SBIN.NS',
                 'BAJFINANCE.NS', 'MARUTI.NS', 'HCLTECH.NS', 'SUNPHARMA.NS',
                 'NTPC.NS', 'WIPRO.NS', 'ADANIENT.NS', 'KOTAKBANK.NS',
                 'AXISBANK.NS', 'TITAN.NS']

INDIA_BENCHMARK_TICKER = '^NSEI'

INDIA_MACRO_TICKERS = ['^INDIAVIX', '^NSEI', 'USDINR=X', 'CL=F']

INDIA_TOTAL_CAPITAL = 1000000

INDIA_REGIME_WEIGHTS = _normalized({
    'risk_on': {
        'momentum': 0.30, 'vol_adj_momentum': 0.25,
        'mean_reversion': 0.05, 'trend': 0.20, 'cross_asset': 0.20,
    },
    'risk_off': {
        'momentum': 0.20, 'vol_adj_momentum': 0.20,
        'mean_reversion': 0.15, 'trend': 0.20, 'cross_asset': 0.25,
    },
    'crisis': {
        'momentum': 0.15, 'vol_adj_momentum': 0.10,
        'mean_reversion': 0.30, 'trend': 0.15, 'cross_asset': 0.30,
    },
})

INDIA_SECTOR_MAP = {
    'it_exporters': ['TCS.NS', 'INFY.NS', 'WIPRO.NS', 'HCLTECH.NS'],
    'banks': ['HDFCBANK.NS', 'ICICIBANK.NS', 'KOTAKBANK.NS', 'AXISBANK.NS', 'SBIN.NS'],
    'consumer': ['HINDUNILVR.NS', 'ITC.NS', 'TITAN.NS', 'MARUTI.NS'],
    'industrial': ['LT.NS', 'NTPC.NS', 'ADANIENT.NS'],
    'telecom': ['BHARTIARTL.NS'],
    'pharma': ['SUNPHARMA.NS'],
    'finance': ['BAJFINANCE.NS'],
    'energy': ['RELIANCE.NS'],
}

INDIA_TILT_STRENGTH = 0.5
INDIA_MIN_WEIGHT = 0.01
INDIA_MAX_WEIGHT = 0.15

US_SECTOR_MAP = {
    'technology': ['AAPL', 'GOOGL', 'MSFT', 'NVDA'],
    'consumer_discretionary': ['AMZN', 'COST'],
    'healthcare': ['JNJ'],
    'consumer_staples': ['KO'],
    'financials': ['BRK-B'],
}

EMERGENCY_TRIGGERS = {
    'us_vix': 40,
    'india_vix': 30,
    'daily_drop_pct': 5,
    'regime_to_crisis': True,
}
MAX_DRAWDOWN_TOLERANCE_PCT = 50

DSR_TRIALS = 37


@dataclass(frozen=True)
class MarketConfig:
    market: str
    tickers: tuple[str, ...]
    benchmark: str
    benchmark_label: str
    macro_tickers: tuple[str, ...]
    vix_ticker: str
    currency: str
    notional_capital: float
    regime_weights: dict[str, dict[str, float]]
    sector_map: dict[str, list[str]]
    max_sector_pct: float
    tilt_strength: float
    min_weight: float
    max_weight: float
    max_single_stock: float
    max_portfolio_beta: float
    max_monthly_cvar: float
    cvar_confidence: float
    transaction_cost: float | None
    risk_free_annual: float | None
    dsr_trials: int


US = MarketConfig(
    market='us',
    tickers=tuple(TICKERS),
    benchmark=BENCHMARK_TICKER,
    benchmark_label='S&P 500',
    macro_tickers=tuple(MACRO_TICKERS),
    vix_ticker='^VIX',
    currency='USD',
    notional_capital=float(TOTAL_CAPITAL),
    regime_weights=REGIME_WEIGHTS,
    sector_map=US_SECTOR_MAP,
    max_sector_pct=0.40,
    tilt_strength=TILT_STRENGTH,
    min_weight=MIN_WEIGHT,
    max_weight=MAX_WEIGHT,
    max_single_stock=0.25,
    max_portfolio_beta=1.5,
    max_monthly_cvar=0.03,
    cvar_confidence=0.95,
    transaction_cost=0.0010,
    risk_free_annual=None,
    dsr_trials=DSR_TRIALS,
)

INDIA = MarketConfig(
    market='india',
    tickers=tuple(INDIA_TICKERS),
    benchmark=INDIA_BENCHMARK_TICKER,
    benchmark_label='Nifty 50',
    macro_tickers=tuple(INDIA_MACRO_TICKERS),
    vix_ticker='^INDIAVIX',
    currency='INR',
    notional_capital=float(INDIA_TOTAL_CAPITAL),
    regime_weights=INDIA_REGIME_WEIGHTS,
    sector_map=INDIA_SECTOR_MAP,
    max_sector_pct=0.30,
    tilt_strength=INDIA_TILT_STRENGTH,
    min_weight=INDIA_MIN_WEIGHT,
    max_weight=INDIA_MAX_WEIGHT,
    max_single_stock=0.15,
    max_portfolio_beta=1.5,
    max_monthly_cvar=0.03,
    cvar_confidence=0.95,
    transaction_cost=None,
    risk_free_annual=0.065,
    dsr_trials=DSR_TRIALS,
)

MARKETS = {'us': US, 'india': INDIA}
