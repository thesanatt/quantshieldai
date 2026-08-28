import json
import re
import zlib
from typing import Any
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest

from quantshield import engine
from quantshield.config import INDIA, MARKETS, US, MarketConfig
from quantshield.costs import delivery_cost
from quantshield.research.backtest import default_cost_fn, flat_cost, india_delivery_cost, walk_forward_backtest
from quantshield.research.portfolio import build_weights
from quantshield.signals.regime import india_detect_regime, us_detect_regime
from quantshield.utils import sanitize

SEED = 11
ROWS = 600
DATES = pd.bdate_range(end='2026-06-30', periods=ROWS)
VOL_TICKERS = {'^VIX', '^VIX3M', '^INDIAVIX'}
BASE_LEVELS = {
    '^NSEI': 20000.0, 'USDINR=X': 84.0, 'CL=F': 75.0, 'GLD': 180.0,
    'UUP': 28.0, 'USO': 72.0, 'HG=F': 4.2, 'GC=F': 2000.0, 'VOO': 450.0,
}
TOP_KEYS = {
    'market', 'generated', 'currency', 'benchmark', 'universe', 'regime', 'weights',
    'walk_forward', 'deflated_sharpe', 'in_sample', 'cvar', 'correlation', 'risk_limits',
}
WEIGHT_KEYS = {
    'ticker', 'weight_pct', 'price', 'momentum', 'vol_adj_momentum', 'mean_reversion',
    'trend', 'cross_asset', 'composite', 'beta',
}
WALK_FORWARD_KEYS = {
    'min_train_days', 'step_days', 'start', 'end', 'total_periods', 'win_periods', 'win_rate',
    'cost_model', 'port_return', 'bench_return', 'alpha', 'port_sharpe', 'bench_sharpe',
    'port_vol', 'bench_vol', 'port_maxdd', 'bench_maxdd', 'alpha_t_stat', 'alpha_p_value',
    'alpha_significant', 'bootstrap_ci', 'periods', 'equity_curve', 'regime_performance',
}
DSR_KEYS = {
    'observed_sharpe_annual', 'benchmark_sharpe_annual', 'expected_max_sharpe_annual', 'n_trials',
    't_obs', 'p_value', 'is_significant', 'skewness', 'excess_kurtosis',
}
IN_SAMPLE_KEYS = {'port_return', 'bench_return', 'alpha', 'port_sharpe', 'bench_sharpe', 'port_maxdd', 'bench_maxdd'}
RISK_LIMIT_KEYS = {'min_weight', 'max_weight', 'max_single_stock', 'max_sector', 'max_portfolio_beta', 'max_monthly_cvar'}
DETECTORS = {'us': us_detect_regime, 'india': india_detect_regime}


def _rng(ticker: str) -> np.random.Generator:
    return np.random.default_rng([SEED, zlib.crc32(ticker.encode())])


def synthetic_series(ticker: str, n: int = ROWS) -> np.ndarray:
    rng = _rng(ticker)
    if ticker in VOL_TICKERS:
        shocks = rng.normal(0.0, 1.5, n)
        level = np.empty(n)
        level[0] = 20.0
        for i in range(1, n):
            level[i] = 20.0 + 0.97 * (level[i - 1] - 20.0) + shocks[i]
        return np.clip(level, 9.0, 60.0)
    if ticker == '^TNX':
        return 4.0 + np.cumsum(rng.normal(0.0, 0.02, n)) * 0.3
    base = BASE_LEVELS.get(ticker, 100.0 + rng.uniform(0.0, 400.0))
    drift = rng.uniform(-0.0002, 0.0008)
    vol = rng.uniform(0.010, 0.022)
    return base * np.cumprod(1.0 + rng.normal(drift, vol, n))


def fake_download(tickers: Any, *args: Any, **kwargs: Any) -> pd.DataFrame:
    names = [tickers] if isinstance(tickers, str) else list(tickers)
    columns = pd.MultiIndex.from_product([['Close', 'Open', 'High', 'Low', 'Volume'], names], names=['Price', 'Ticker'])
    frame = pd.DataFrame(index=DATES, columns=columns, dtype=float)
    for t in names:
        series = synthetic_series(t)
        for field in ('Close', 'Open', 'High', 'Low'):
            frame[(field, t)] = series
        frame[('Volume', t)] = 1_000_000.0
    return frame


def synthetic_panel(cfg: MarketConfig) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.Series]:
    with patch('yfinance.download', fake_download):
        return engine.download_data(cfg)


def _none_paths(obj: Any, path: str = '') -> list[str]:
    if obj is None:
        return [path]
    if isinstance(obj, dict):
        return [p for k, v in obj.items() for p in _none_paths(v, f'{path}.{k}')]
    if isinstance(obj, list):
        return [p for i, v in enumerate(obj) for p in _none_paths(v, f'{path}[{i}]')]
    return []


@pytest.fixture(scope='module')
def outputs() -> dict[str, dict]:
    with patch('yfinance.download', fake_download), \
            patch('quantshield.engine.decompose_returns', return_value={'error': 'offline'}):
        return {market: sanitize(engine.run(cfg)) for market, cfg in MARKETS.items()}


@pytest.mark.parametrize('market', ['us', 'india'])
class TestGoldenOutput:
    def test_top_level_contract(self, outputs, market):
        out = outputs[market]
        assert set(out) == TOP_KEYS
        cfg = MARKETS[market]
        assert out['market'] == market
        assert out['currency'] == cfg.currency
        assert out['benchmark'] == {'ticker': cfg.benchmark, 'label': cfg.benchmark_label}
        assert re.fullmatch(r'\d{4}-\d{2}-\d{2}', out['generated'])
        assert sorted(out['universe']) == sorted(cfg.tickers)
        assert set(out['in_sample']) == IN_SAMPLE_KEYS
        assert set(out['cvar']) == {'portfolio_cvar', 'var', 'confidence'}
        assert set(out['correlation']) == {'avg_30d', 'warning', 'top_pairs'}
        assert set(out['risk_limits']) == RISK_LIMIT_KEYS
        assert out['risk_limits']['max_sector'] == cfg.max_sector_pct
        assert isinstance(out['correlation']['warning'], bool)

    def test_regime_block(self, outputs, market):
        regime = outputs[market]['regime']
        assert set(regime) == {'detected', 'confidence', 'vix', 'signal_weights'}
        assert regime['detected'] in ('risk_on', 'risk_off', 'crisis')
        assert 0.0 <= regime['confidence'] <= 1.0
        assert regime['vix'] > 0
        assert abs(sum(regime['signal_weights'].values()) - 1.0) < 1e-6
        assert regime['signal_weights'] == MARKETS[market].regime_weights[regime['detected']]

    def test_weights_respect_limits(self, outputs, market):
        cfg = MARKETS[market]
        rows = outputs[market]['weights']
        assert len(rows) == len(cfg.tickers)
        assert all(set(r) == WEIGHT_KEYS for r in rows)
        pct = [r['weight_pct'] for r in rows]
        assert pct == sorted(pct, reverse=True)
        assert abs(sum(pct) - 100.0) < 0.05
        cap = min(cfg.max_weight, cfg.max_single_stock) * 100
        for r in rows:
            assert cfg.min_weight * 100 - 0.01 <= r['weight_pct'] <= cap + 0.01, r
            assert r['price'] > 0
            assert -1.0 <= r['composite'] <= 1.0
        by_ticker = {r['ticker']: r['weight_pct'] for r in rows}
        for sector, members in cfg.sector_map.items():
            assert sum(by_ticker.get(t, 0.0) for t in members) <= cfg.max_sector_pct * 100 + 0.02, sector

    def test_walk_forward_block(self, outputs, market):
        wf = outputs[market]['walk_forward']
        assert WALK_FORWARD_KEYS <= set(wf)
        assert wf['min_train_days'] == 252 and wf['step_days'] == 21
        expected_periods = (ROWS - 1 - 252) // 21
        assert expected_periods == 16
        assert wf['total_periods'] == expected_periods
        assert len(wf['periods']) == expected_periods
        assert wf['fallback_periods'] == 0
        assert wf['win_periods'] == sum(1 for p in wf['periods'] if p['alpha'] > 0)
        assert abs(wf['alpha'] - round(wf['port_return'] - wf['bench_return'], 2)) <= 0.011
        assert wf['port_maxdd'] <= 0 and wf['bench_maxdd'] <= 0
        assert 0 <= wf['alpha_p_value'] <= 1
        assert wf['bootstrap_ci']['n_bootstrap'] == 10000
        assert wf['bootstrap_ci']['ci_level'] == 0.95
        assert wf['start'] == wf['periods'][0]['period_start']
        assert wf['end'] == wf['periods'][-1]['period_end']
        for prev, nxt in zip(wf['periods'], wf['periods'][1:], strict=False):
            assert prev['period_end'] < nxt['period_start']
        assert set(wf['regime_performance']) == {p['regime'] for p in wf['periods']}
        assert sum(v['n_months'] for v in wf['regime_performance'].values()) == expected_periods

    def test_equity_curve(self, outputs, market):
        curve = outputs[market]['walk_forward']['equity_curve']
        assert curve[0]['portfolio'] == 100.0 and curve[0]['benchmark'] == 100.0
        assert 2 <= len(curve) <= 400
        dates = [p['date'] for p in curve]
        assert dates == sorted(dates) and len(set(dates)) == len(dates)
        assert curve[0]['date'] < outputs[market]['walk_forward']['start']
        assert curve[-1]['date'] == outputs[market]['walk_forward']['end']
        wf = outputs[market]['walk_forward']
        assert abs(curve[-1]['portfolio'] - 100.0 * (1 + wf['port_return'] / 100)) < 0.02
        assert abs(curve[-1]['benchmark'] - 100.0 * (1 + wf['bench_return'] / 100)) < 0.02

    def test_deflated_sharpe(self, outputs, market):
        dsr = outputs[market]['deflated_sharpe']
        assert DSR_KEYS <= set(dsr)
        assert 0.0 <= dsr['p_value'] <= 1.0
        assert dsr['n_trials'] == MARKETS[market].dsr_trials == 37
        assert dsr['t_obs'] == 16 * 21
        assert dsr['observed_sharpe_annual'] == outputs[market]['walk_forward']['port_sharpe']
        assert dsr['is_significant'] is (dsr['p_value'] < 0.05)
        assert dsr['psr'] == pytest.approx(1.0 - dsr['p_value'], abs=1e-6)

    def test_no_nan_no_legacy_names(self, outputs, market):
        out = outputs[market]
        assert _none_paths(out) == []
        text = json.dumps(out)
        assert 'voo_' not in text
        assert '\u2014' not in text
        assert 'fama_french' not in out


def test_fama_french_included_only_with_real_factors():
    real = {'alpha': 0.001, 'alpha_tstat': 1.2, 'factor_betas': {}, 'n_months': 16}
    with patch('yfinance.download', fake_download), \
            patch('quantshield.engine.decompose_returns', return_value=real) as decompose:
        out = engine.run(US)
    assert out['fama_french'] == real
    monthly = decompose.call_args.args[0]
    assert isinstance(monthly, pd.Series)
    assert monthly.index.is_month_end.all()
    assert 12 <= len(monthly) <= 17
    synthetic = dict(real, is_synthetic=True)
    with patch('yfinance.download', fake_download), \
            patch('quantshield.engine.decompose_returns', return_value=synthetic):
        out = engine.run(US)
    assert 'fama_french' not in out


def test_calendar_month_returns_compound_full_months_only():
    dates = pd.bdate_range('2025-01-20', '2025-03-31')
    daily = pd.Series(0.01, index=dates)
    monthly = engine.calendar_month_returns(daily)
    assert list(monthly.index.strftime('%Y-%m')) == ['2025-02', '2025-03']
    feb_sessions = int((dates.month == 2).sum())
    assert monthly.iloc[0] == pytest.approx(1.01 ** feb_sessions - 1)
    assert engine.calendar_month_returns(daily, min_sessions=5).index[0].month == 1


def test_skip_walk_forward_leaves_placeholders():
    with patch('yfinance.download', fake_download):
        out = sanitize(engine.run(INDIA, skip_walk_forward=True))
    assert set(out) == TOP_KEYS
    assert out['walk_forward'] is None
    assert out['deflated_sharpe'] is None
    assert abs(sum(r['weight_pct'] for r in out['weights']) - 100.0) < 0.05


def test_cli_writes_file_and_prints_json(tmp_path, capsys, monkeypatch):
    out_path = tmp_path / 'nested' / 'us.json'
    monkeypatch.setattr('sys.argv', ['engine', '--market', 'us', '--skip-walk-forward', '--out', str(out_path)])
    with patch('yfinance.download', fake_download):
        engine.main()
    captured = capsys.readouterr()
    printed = json.loads(captured.out)
    assert printed == json.loads(out_path.read_text())
    assert printed['market'] == 'us'
    assert printed['walk_forward'] is None
    assert captured.out.lstrip().startswith('{')
    assert 'wrote' in captured.err


def test_cli_rejects_unknown_market(monkeypatch):
    monkeypatch.setattr('sys.argv', ['engine', '--market', 'uk'])
    with pytest.raises(SystemExit):
        engine.main()


def test_download_drops_sparse_tickers_and_forward_fills():
    def download_with_gaps(tickers: Any, *args: Any, **kwargs: Any) -> pd.DataFrame:
        frame = fake_download(tickers, *args, **kwargs)
        names = [tickers] if isinstance(tickers, str) else list(tickers)
        if 'KO' in names:
            frame[('Close', 'KO')] = np.nan
            frame.loc[DATES[100], ('Close', 'AAPL')] = np.nan
            frame.loc[DATES[:60], ('Close', 'MSFT')] = np.nan
        if '^VIX3M' in names:
            frame.loc[DATES[:-1], ('Close', '^VIX3M')] = np.nan
        return frame

    with patch('yfinance.download', download_with_gaps):
        close, returns, macro_close, bench = engine.download_data(US)
    assert 'KO' not in close.columns
    assert 'MSFT' in close.columns
    assert len(close.columns) == len(US.tickers) - 1
    assert len(close) == ROWS - 60
    assert not close.isna().any().any()
    assert close.loc[DATES[100], 'AAPL'] == close.loc[DATES[99], 'AAPL']
    assert len(returns) == len(close) - 1
    assert bench.name == US.benchmark
    assert set(macro_close.columns) == set(US.macro_tickers) - {'^VIX3M'}
    assert len(macro_close) == ROWS


def test_download_empty_raises():
    with patch('yfinance.download', return_value=pd.DataFrame()):
        with pytest.raises(RuntimeError):
            engine.download_data(US)


def test_round_pct_sums_to_exactly_100():
    weights = pd.Series([1 / 3, 1 / 3, 1 / 3], index=['A', 'B', 'C'])
    rounded = engine._round_pct(weights)
    assert rounded.sum() == 100.0
    assert (rounded - weights * 100).abs().max() < 0.01
    weights = pd.Series(np.random.default_rng(3).dirichlet(np.ones(20)))
    rounded = engine._round_pct(weights)
    assert (rounded * 100).round().sum() == 10000
    assert (rounded - weights * 100).abs().max() < 0.01


class TestLookAhead:
    @pytest.mark.parametrize('market', ['us', 'india'])
    def test_build_weights_ignores_future_rows(self, market):
        cfg = MARKETS[market]
        close, returns, macro_close, bench = synthetic_panel(cfg)
        cut = 400
        rng = np.random.default_rng(5)
        future = close.copy()
        future.iloc[cut:] *= 1.0 + rng.uniform(-0.3, 0.3, size=future.iloc[cut:].shape)
        future_returns = future.pct_change().dropna()
        future_macro = macro_close.copy()
        future_macro.iloc[cut:] *= 1.5
        train_end = close.index[cut - 1]

        base, _ = build_weights(
            close.loc[:train_end], returns.loc[:train_end], macro_close.loc[:train_end],
            bench.loc[:train_end], cfg, 'risk_on',
        )
        perturbed, _ = build_weights(
            future.loc[:train_end], future_returns.loc[:train_end], future_macro.loc[:train_end],
            bench.loc[:train_end], cfg, 'risk_on',
        )
        pd.testing.assert_series_equal(base, perturbed)
        whole, _ = build_weights(future, future_returns, future_macro, bench, cfg, 'risk_on')
        assert not np.allclose(base.values, whole.reindex(base.index).values)

    def test_walk_forward_periods_before_perturbation_unchanged(self):
        close, returns, macro_close, bench = synthetic_panel(US)
        cut = 450
        future = close.copy()
        future.iloc[cut:] *= 1.0 + np.random.default_rng(9).uniform(-0.2, 0.2, size=future.iloc[cut:].shape)
        future_returns = future.pct_change().dropna()

        base = walk_forward_backtest(close, returns, macro_close, bench, US, us_detect_regime)
        shifted = walk_forward_backtest(future, future_returns, macro_close, bench, US, us_detect_regime)
        cutoff = close.index[cut].strftime('%Y-%m-%d')
        before = [p for p in base['periods'] if p['period_end'] < cutoff]
        assert len(before) >= 5
        assert before == shifted['periods'][:len(before)]
        after = [p for p in base['periods'] if p['period_start'] >= cutoff]
        assert after != shifted['periods'][-len(after):]


class TestTransactionCosts:
    def test_flat_cost_is_turnover_times_bps(self):
        prev = pd.Series({'A': 0.5, 'B': 0.5})
        new = pd.Series({'A': 0.6, 'B': 0.4})
        assert flat_cost(10.0)(prev, new, 100000.0) == pytest.approx(0.1 * 10 / 10000, abs=1e-15)
        assert flat_cost(10.0)(prev, prev, 100000.0) == 0.0
        entered = pd.Series({'A': 0.6, 'C': 0.4})
        assert flat_cost(25.0)(prev, entered, 100000.0) == pytest.approx(0.5 * 25 / 10000, abs=1e-15)

    def test_india_cost_equals_summed_delivery_legs(self):
        prev = pd.Series({'NIFTYBEES.NS': 0.5, 'TCS.NS': 0.5})
        new = pd.Series({'NIFTYBEES.NS': 0.4, 'TCS.NS': 0.45, 'INFY.NS': 0.15})
        capital = 1_000_000.0
        expected = (
            delivery_cost('SELL', 100_000.0, etf=True)
            + delivery_cost('SELL', 50_000.0)
            + delivery_cost('BUY', 150_000.0)
        ) / capital
        assert india_delivery_cost(prev, new, capital) == pytest.approx(expected, abs=1e-15)
        assert india_delivery_cost(prev, prev, capital) == 0.0

    def test_india_default_more_expensive_than_us_flat_for_equity_legs(self):
        prev = pd.Series({'TCS.NS': 0.5, 'INFY.NS': 0.5})
        new = pd.Series({'TCS.NS': 0.6, 'INFY.NS': 0.4})
        assert india_delivery_cost(prev, new, 1_000_000.0) > flat_cost(10.0)(prev, new, 1_000_000.0)

    def test_walk_forward_charges_each_rebalance_once(self):
        close, returns, macro_close, bench = synthetic_panel(US)
        calls: list[tuple[pd.Series, pd.Series]] = []

        def recording(prev: pd.Series, new: pd.Series, capital: float) -> float:
            calls.append((prev, new))
            assert capital == US.notional_capital
            return 0.001

        free = walk_forward_backtest(close, returns, macro_close, bench, US, us_detect_regime, cost_fn=lambda p, n, c: 0.0)
        charged = walk_forward_backtest(close, returns, macro_close, bench, US, us_detect_regime, cost_fn=recording)
        assert len(calls) == charged['total_periods']
        assert charged['cost_model'] == 'custom'
        diff = charged['daily_returns'] - free['daily_returns']
        first_days = free['daily_returns'].index[::21]
        assert np.allclose(diff.loc[first_days].values, -0.001)
        assert np.allclose(diff.drop(first_days).values, 0.0)
        assert charged['port_return'] < free['port_return']
        assert (calls[0][0] == 0.0).all()
        index = free['daily_returns'].index
        for k in range(1, len(calls)):
            window = returns.loc[index[(k - 1) * 21:k * 21]]
            growth = (1.0 + window).cumprod()
            target = calls[k - 1][1]
            value = (growth * target).sum(axis=1)
            drifted = growth.iloc[-1] * target / float(value.iloc[-1])
            pd.testing.assert_series_equal(calls[k][0], drifted, check_names=False)

    def test_us_default_cost_is_hand_computed_turnover_times_ten_bps(self) -> None:
        close, returns, macro_close, bench = synthetic_panel(US)
        seen: list[tuple[pd.Series, pd.Series]] = []
        default_fn, _ = default_cost_fn(US)

        def recording(prev: pd.Series, new: pd.Series, capital: float) -> float:
            seen.append((prev.copy(), new.copy()))
            return default_fn(prev, new, capital)

        free = walk_forward_backtest(close, returns, macro_close, bench, US, us_detect_regime, cost_fn=lambda p, n, c: 0.0)
        charged = walk_forward_backtest(close, returns, macro_close, bench, US, us_detect_regime, cost_fn=recording)
        expected = walk_forward_backtest(close, returns, macro_close, bench, US, us_detect_regime)
        pd.testing.assert_series_equal(charged['daily_returns'], expected['daily_returns'])
        assert expected['cost_model'] == 'flat 10 bps per unit of one-way turnover'
        first_days = free['daily_returns'].index[::21]
        assert len(seen) == len(first_days) == charged['total_periods']
        diff = (free['daily_returns'] - charged['daily_returns']).loc[first_days]
        hand = [0.5 * float((new - prev).abs().sum()) * 10.0 / 10000.0 for prev, new in seen]
        assert all(h > 0 for h in hand)
        np.testing.assert_allclose(diff.values, hand, rtol=0, atol=1e-15)

    def test_india_default_cost_is_hand_computed_delivery_legs(self) -> None:
        close, returns, macro_close, bench = synthetic_panel(INDIA)
        seen: list[tuple[pd.Series, pd.Series]] = []
        default_fn, label = default_cost_fn(INDIA)

        def recording(prev: pd.Series, new: pd.Series, capital: float) -> float:
            assert capital == 1_000_000.0
            seen.append((prev.copy(), new.copy()))
            return default_fn(prev, new, capital)

        def hand_leg(action: str, value: float) -> float:
            txn = value * 0.0000297
            sebi = value * 0.000001
            gst = 0.18 * (txn + sebi)
            if action == 'BUY':
                return value * 0.001 + value * 0.00015 + txn + sebi + gst
            return value * 0.001 + txn + sebi + gst + 15.93

        free = walk_forward_backtest(close, returns, macro_close, bench, INDIA, india_detect_regime, cost_fn=lambda p, n, c: 0.0)
        charged = walk_forward_backtest(close, returns, macro_close, bench, INDIA, india_detect_regime, cost_fn=recording)
        assert label.startswith('NSE CNC delivery schedule')
        first_days = free['daily_returns'].index[::21]
        diff = (free['daily_returns'] - charged['daily_returns']).loc[first_days]
        hand = []
        for prev, new in seen:
            delta = (new - prev) * 1_000_000.0
            legs = sum(hand_leg('BUY', float(v)) for v in delta[delta > 0])
            legs += sum(hand_leg('SELL', float(-v)) for v in delta[delta < 0])
            hand.append(legs / 1_000_000.0)
        assert all(h > 15.93 / 1_000_000.0 for h in hand)
        np.testing.assert_allclose(diff.values, hand, rtol=0, atol=1e-15)

    @pytest.mark.parametrize('market', ['us', 'india'])
    def test_default_cost_model_reduces_return(self, market):
        cfg = MARKETS[market]
        close, returns, macro_close, bench = synthetic_panel(cfg)
        free = walk_forward_backtest(close, returns, macro_close, bench, cfg, DETECTORS[market], cost_fn=lambda p, n, c: 0.0)
        charged = walk_forward_backtest(close, returns, macro_close, bench, cfg, DETECTORS[market])
        assert charged['port_return'] < free['port_return']
        assert charged['bench_return'] == free['bench_return']
        expected = 'CNC' if market == 'india' else 'flat 10 bps'
        assert expected in charged['cost_model']
