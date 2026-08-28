import os
import shutil
import sys
import tempfile
from collections.abc import Iterator
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
GUARDED_DIRS = (
    'data/portfolio', 'data/monitor', 'data/journal', 'data/intraday',
    'dashboard/public', 'dashboard/src/data',
)
TEST_ROOT_SUBDIRS = (
    'data/portfolio', 'data/monitor', 'data/journal', 'data/intraday', 'data/research',
    'dashboard/public/live', 'dashboard/src/data',
)

if 'quantshield.paths' in sys.modules:
    raise RuntimeError('quantshield.paths was imported before tests/conftest.py could redirect QUANTSHIELD_ROOT')

TEST_ROOT = Path(tempfile.mkdtemp(prefix='quantshield-test-root-')).resolve()
os.environ['QUANTSHIELD_ROOT'] = str(TEST_ROOT)
for _sub in TEST_ROOT_SUBDIRS:
    (TEST_ROOT / _sub).mkdir(parents=True, exist_ok=True)


def pytest_configure(config: pytest.Config) -> None:
    from quantshield import paths

    if paths.ROOT.resolve() != TEST_ROOT:
        raise pytest.UsageError(f'quantshield.paths.ROOT is {paths.ROOT}, expected the test root {TEST_ROOT}')


def tree_snapshot() -> dict[str, int]:
    snapshot: dict[str, int] = {}
    for rel in GUARDED_DIRS:
        base = REPO_ROOT / rel
        if not base.exists():
            continue
        for dirpath, _dirs, files in os.walk(base):
            for name in files:
                path = Path(dirpath) / name
                snapshot[str(path.relative_to(REPO_ROOT))] = path.stat().st_mtime_ns
    return snapshot


def describe_changes(before: dict[str, int], after: dict[str, int]) -> list[str]:
    changes = [f'created: {p}' for p in sorted(set(after) - set(before))]
    changes += [f'deleted: {p}' for p in sorted(set(before) - set(after))]
    changes += [f'modified: {p}' for p in sorted(set(before) & set(after)) if before[p] != after[p]]
    return changes


@pytest.fixture(scope='session', autouse=True)
def guarded_repo_tree(request: pytest.FixtureRequest) -> dict[str, int]:
    before = tree_snapshot()

    def verify() -> None:
        changes = describe_changes(before, tree_snapshot())
        if changes:
            pytest.fail(
                'the test session touched the real repository data tree:\n  ' + '\n  '.join(changes),
                pytrace=False,
            )

    request.addfinalizer(verify)
    return before


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    shutil.rmtree(TEST_ROOT, ignore_errors=True)


DEFAULT_TICKERS = ('AAPL', 'GOOGL', 'AMZN', 'COST', 'JNJ', 'KO')
US_MACRO_TICKERS = ('^VIX', '^TNX', 'GLD', 'UUP', 'USO')
INDIA_MACRO_TICKERS = ('^INDIAVIX', '^NSEI', 'USDINR=X', 'CL=F')


def make_dates(periods: int = 300, end: str = '2025-01-15') -> pd.DatetimeIndex:
    return pd.bdate_range(end=end, periods=periods)


def make_prices(
    periods: int = 300,
    tickers: tuple[str, ...] = DEFAULT_TICKERS,
    seed: int = 42,
    drift: float = 0.0005,
    vol: float = 0.02,
) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    dates = make_dates(periods)
    data = {}
    for ticker in tickers:
        base = rng.uniform(50.0, 400.0)
        data[ticker] = base * np.cumprod(1.0 + rng.normal(drift, vol, periods))
    return pd.DataFrame(data, index=dates)


def make_returns(
    periods: int = 300,
    tickers: tuple[str, ...] = DEFAULT_TICKERS,
    seed: int = 42,
    mean: float = 0.0005,
    vol: float = 0.02,
) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    return pd.DataFrame({t: rng.normal(mean, vol, periods) for t in tickers}, index=make_dates(periods))


def make_macro(periods: int = 300, market: str = 'us', seed: int = 123) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    dates = make_dates(periods)
    if market == 'us':
        data = {
            '^VIX': rng.uniform(12.0, 30.0, periods),
            '^TNX': rng.uniform(3.5, 4.5, periods),
            'GLD': np.linspace(170.0, 190.0, periods),
            'UUP': np.linspace(27.0, 28.0, periods),
            'USO': np.linspace(70.0, 75.0, periods),
        }
    elif market == 'india':
        data = {
            '^INDIAVIX': rng.uniform(11.0, 20.0, periods),
            '^NSEI': 22000.0 * np.cumprod(1.0 + rng.normal(0.0003, 0.008, periods)),
            'USDINR=X': 84.0 + rng.normal(0.0, 0.1, periods),
            'CL=F': 75.0 + rng.normal(0.0, 0.5, periods),
        }
    else:
        raise ValueError(f'unknown market: {market}')
    return pd.DataFrame(data, index=dates)


def make_benchmark(periods: int = 300, seed: int = 99, drift: float = 0.0004, vol: float = 0.015) -> pd.Series:
    rng = np.random.default_rng(seed)
    close = pd.Series(100.0 * np.cumprod(1.0 + rng.normal(drift, vol, periods)), index=make_dates(periods), name='VOO')
    return close.pct_change().dropna()


def flat_macro(dates: pd.DatetimeIndex, **levels: float) -> pd.DataFrame:
    return pd.DataFrame({k: np.full(len(dates), v) for k, v in levels.items()}, index=dates)


@pytest.fixture
def repo_root() -> Path:
    return REPO_ROOT


@pytest.fixture
def dates_300() -> pd.DatetimeIndex:
    return make_dates(300)


@pytest.fixture
def prices() -> pd.DataFrame:
    return make_prices()


@pytest.fixture
def returns(prices: pd.DataFrame) -> pd.DataFrame:
    return prices.pct_change().dropna()


@pytest.fixture
def benchmark_returns() -> pd.Series:
    return make_benchmark()


@pytest.fixture
def macro_close() -> pd.DataFrame:
    return make_macro()


@pytest.fixture
def prices_short() -> pd.DataFrame:
    return make_prices(periods=10, tickers=('AAPL', 'GOOGL'), seed=99)


@pytest.fixture
def prices_single_ticker() -> pd.DataFrame:
    return make_prices(tickers=('SOLO',), seed=7, drift=0.0003, vol=0.015)


@pytest.fixture
def prices_flat(dates_300: pd.DatetimeIndex) -> pd.DataFrame:
    return pd.DataFrame({t: np.full(len(dates_300), 100.0) for t in ('FLAT_A', 'FLAT_B', 'FLAT_C')}, index=dates_300)


@pytest.fixture
def returns_zero(dates_300: pd.DatetimeIndex) -> pd.DataFrame:
    return pd.DataFrame({t: np.zeros(len(dates_300)) for t in ('ZERO_A', 'ZERO_B', 'ZERO_C')}, index=dates_300)


@pytest.fixture
def returns_perfect_corr(dates_300: pd.DatetimeIndex) -> pd.DataFrame:
    base = np.random.default_rng(55).normal(0.001, 0.02, len(dates_300))
    return pd.DataFrame({'CORR_A': base, 'CORR_B': base, 'CORR_C': base}, index=dates_300)


def walk_keys(obj: object) -> Iterator[str]:
    if isinstance(obj, dict):
        for key, value in obj.items():
            yield str(key)
            yield from walk_keys(value)
    elif isinstance(obj, list):
        for value in obj:
            yield from walk_keys(value)
