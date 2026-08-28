import json

import numpy as np
import pandas as pd
import pytest

from quantshield.config import US
from quantshield.research.backtest import (
    _daily_rf,
    _perf_stats,
    backtest,
    bootstrap_confidence_intervals,
    default_cost_fn,
    regime_conditional_performance,
    walk_forward_backtest,
)
from quantshield.signals.regime import us_detect_regime
from quantshield.utils import sanitize
from tests.test_engine_cli import synthetic_panel

REQUIRED = [
    'min_train_days', 'step_days', 'start', 'end', 'total_periods', 'win_periods', 'win_rate',
    'fallback_periods', 'cost_model', 'port_return', 'bench_return', 'alpha', 'port_sharpe',
    'bench_sharpe', 'port_vol', 'bench_vol', 'port_maxdd', 'bench_maxdd', 'alpha_t_stat',
    'alpha_p_value', 'alpha_significant', 'bootstrap_ci', 'periods', 'equity_curve', 'daily_returns',
]


@pytest.fixture(scope='module')
def panel():
    return synthetic_panel(US)


@pytest.fixture(scope='module')
def result(panel):
    close, returns, macro_close, bench = panel
    return walk_forward_backtest(close, returns, macro_close, bench, US, us_detect_regime)


class TestWalkForwardSummary:
    def test_required_keys_and_bench_naming(self, result):
        for key in REQUIRED:
            assert key in result, key
        assert not any('voo' in k for k in result)
        assert not any('voo' in k for p in result['periods'] for k in p)

    def test_period_count_matches_expanding_schedule(self, panel, result):
        _, returns, _, _ = panel
        assert result['total_periods'] == (len(returns) - 252) // 21
        assert len(result['daily_returns']) == result['total_periods'] * 21
        assert result['fallback_periods'] == 0

    def test_periods_are_contiguous_and_after_training(self, panel, result):
        _, returns, _, _ = panel
        first_allowed = returns.index[252].strftime('%Y-%m-%d')
        assert result['periods'][0]['period_start'] == first_allowed
        for prev, nxt in zip(result['periods'], result['periods'][1:], strict=False):
            assert prev['period_end'] < nxt['period_start']
        for p in result['periods']:
            assert set(p) == {'period_start', 'period_end', 'port_return', 'bench_return', 'alpha', 'regime'}
            assert p['regime'] in ('risk_on', 'risk_off', 'crisis')
            assert p['alpha'] == pytest.approx(p['port_return'] - p['bench_return'], abs=0.011)

    def test_summary_consistent_with_daily_series(self, result):
        daily = result['daily_returns']
        assert isinstance(daily, pd.Series)
        compounded = float(np.prod(1 + daily.values) - 1) * 100
        assert result['port_return'] == pytest.approx(compounded, abs=0.011)
        assert result['alpha'] == pytest.approx(result['port_return'] - result['bench_return'], abs=0.011)
        assert result['win_periods'] == sum(1 for p in result['periods'] if p['alpha'] > 0)
        assert result['win_rate'] == pytest.approx(result['win_periods'] / result['total_periods'] * 100, abs=0.06)
        assert result['port_maxdd'] <= 0 and result['bench_maxdd'] <= 0
        assert 0 <= result['alpha_p_value'] <= 1
        assert result['alpha_significant'] is (result['alpha_p_value'] < 0.05)

    def test_sharpe_uses_treasury_rate(self, panel, result):
        _, _, macro_close, _ = panel
        daily = result['daily_returns'].values
        values = np.concatenate(([1.0], np.cumprod(1 + daily)))
        rf = _daily_rf(macro_close, US.risk_free_annual)
        assert rf > 0
        assert _perf_stats(values, rf)['sharpe'] == result['port_sharpe']
        assert _perf_stats(values, 0.0)['sharpe'] != result['port_sharpe']

    def test_equity_curve_indexed_to_100(self, result):
        curve = result['equity_curve']
        assert curve[0] == {'date': curve[0]['date'], 'portfolio': 100.0, 'benchmark': 100.0}
        assert curve[0]['date'] < result['start']
        assert curve[-1]['date'] == result['end']
        assert len(curve) == result['total_periods'] * 21 + 1
        assert curve[-1]['portfolio'] == pytest.approx(100 * (1 + result['port_return'] / 100), abs=0.02)

    def test_equity_curve_capped_at_400_points(self, panel):
        close, returns, macro_close, bench = panel
        res = walk_forward_backtest(close, returns, macro_close, bench, US, us_detect_regime, min_train_days=100, step_days=5)
        assert res['total_periods'] * 5 + 1 > 400
        curve = res['equity_curve']
        assert len(curve) <= 400
        assert curve[0]['portfolio'] == 100.0
        assert curve[-1]['date'] == res['end']

    def test_json_serializable_after_dropping_series(self, result):
        summary = {k: v for k, v in result.items() if k != 'daily_returns'}
        parsed = json.loads(json.dumps(sanitize(summary)))
        assert parsed['total_periods'] == result['total_periods']

    def test_insufficient_data_returns_none(self, panel):
        close, returns, macro_close, bench = panel
        short = walk_forward_backtest(close.iloc[:200], returns.iloc[:199], macro_close, bench, US, us_detect_regime)
        assert short is None

    def test_detector_failure_counts_fallbacks_and_uses_equal_weights(self, panel):
        close, returns, macro_close, bench = panel

        def broken(macro: pd.DataFrame) -> tuple[str, float, dict]:
            raise ValueError('no macro data')

        res = walk_forward_backtest(close, returns, macro_close, bench, US, broken, cost_fn=lambda p, n, c: 0.0)
        assert res['fallback_periods'] == res['total_periods']
        assert {p['regime'] for p in res['periods']} == {'unknown'}
        window = returns.loc[res['daily_returns'].index]
        chunks = []
        for k in range(0, len(window), 21):
            growth = (1.0 + window.iloc[k:k + 21]).cumprod()
            value = growth.mean(axis=1)
            chunks.append(value / value.shift(1).fillna(1.0) - 1.0)
        pd.testing.assert_series_equal(res['daily_returns'], pd.concat(chunks), check_names=False)

    def test_default_cost_labels(self):
        fn, label = default_cost_fn(US)
        assert label == 'flat 10 bps per unit of one-way turnover'
        assert fn(pd.Series({'A': 1.0}), pd.Series({'A': 1.0}), 1.0) == 0.0


class TestInSampleBacktest:
    def test_keys_and_alpha(self, panel):
        close, returns, macro_close, bench = panel
        weights = pd.Series(1.0 / len(close.columns), index=close.columns)
        bt = backtest(returns, weights, macro_close, benchmark_returns=bench, total_capital=100000)
        for key in ('port_return', 'bench_return', 'alpha', 'port_sharpe', 'bench_sharpe',
                    'port_vol', 'bench_vol', 'port_maxdd', 'bench_maxdd', 'port_final', 'bench_final'):
            assert key in bt
        assert bt['alpha'] == pytest.approx(bt['port_return'] - bt['bench_return'], abs=0.011)
        assert bt['port_final'] == pytest.approx(100000 * (1 + bt['port_return'] / 100), abs=10)
        assert bt['port_maxdd'] <= 0

    def test_rf_override_changes_sharpe(self, panel):
        close, returns, macro_close, bench = panel
        weights = pd.Series(1.0 / len(close.columns), index=close.columns)
        low = backtest(returns, weights, macro_close, benchmark_returns=bench, daily_rf=0.0)
        high = backtest(returns, weights, macro_close, benchmark_returns=bench, daily_rf=0.10 / 252)
        assert high['port_sharpe'] < low['port_sharpe']
        assert high['port_return'] == low['port_return']

    def test_window_respected(self, panel):
        close, returns, macro_close, bench = panel
        weights = pd.Series(1.0 / len(close.columns), index=close.columns)
        bt = backtest(returns, weights, macro_close, days=100, benchmark_returns=bench)
        assert bt['start'] == returns.index[-100].strftime('%Y-%m-%d')
        assert bt['end'] == returns.index[-1].strftime('%Y-%m-%d')


class TestHelpers:
    def test_perf_stats_known_values(self):
        values = np.array([1.0, 1.1, 1.05, 1.155])
        stats = _perf_stats(values, 0.0)
        assert stats['return'] == pytest.approx(15.5, abs=0.011)
        assert stats['maxdd'] == pytest.approx((1.05 / 1.1 - 1) * 100, abs=0.011)
        rets = np.array([0.1, -1 / 22, 0.1])
        assert stats['vol'] == pytest.approx(np.std(rets, ddof=1) * np.sqrt(252) * 100, abs=0.011)
        assert stats['sharpe'] == pytest.approx(rets.mean() / np.std(rets, ddof=1) * np.sqrt(252), abs=0.011)

    def test_perf_stats_flat_series(self):
        stats = _perf_stats(np.ones(10), 0.0)
        assert stats == {'return': 0.0, 'sharpe': 0.0, 'vol': 0.0, 'maxdd': 0.0}

    def test_daily_rf_sources(self):
        macro = pd.DataFrame({'^TNX': [3.0, 4.5]})
        assert _daily_rf(macro) == pytest.approx(0.045 / 252)
        assert _daily_rf(macro, 0.065) == pytest.approx(0.065 / 252)
        assert _daily_rf(pd.DataFrame({'GLD': [1.0]})) == 0.0
        assert _daily_rf(pd.DataFrame({'^TNX': [np.nan, np.nan]})) == 0.0


class TestBootstrapCI:
    def test_structure_and_ordering(self):
        rng = np.random.default_rng(42)
        port = pd.Series(rng.normal(0.01, 0.03, 36))
        bench = pd.Series(rng.normal(0.005, 0.025, 36))
        res = bootstrap_confidence_intervals(port, bench)
        assert set(res) == {'sharpe_ci', 'alpha_ci', 'alpha_includes_zero', 'n_bootstrap', 'ci_level'}
        assert res['sharpe_ci'][0] <= res['sharpe_ci'][1]
        assert res['alpha_ci'][0] <= res['alpha_ci'][1]
        assert res['n_bootstrap'] == 10000 and res['ci_level'] == 0.95
        json.dumps(sanitize(res))

    def test_deterministic(self):
        rng = np.random.default_rng(1)
        port = pd.Series(rng.normal(0.01, 0.03, 36))
        bench = pd.Series(rng.normal(0.005, 0.025, 36))
        assert bootstrap_confidence_intervals(port, bench) == bootstrap_confidence_intervals(port, bench)

    def test_strong_alpha_excludes_zero(self):
        rng = np.random.default_rng(42)
        port = pd.Series(rng.normal(0.05, 0.01, 100))
        bench = pd.Series(rng.normal(0.0, 0.01, 100))
        assert bootstrap_confidence_intervals(port, bench)['alpha_includes_zero'] is False

    def test_zero_alpha_includes_zero(self):
        rng = np.random.default_rng(42)
        shared = rng.normal(0.01, 0.03, 100)
        port = pd.Series(shared + rng.normal(0, 0.001, 100))
        assert bootstrap_confidence_intervals(port, pd.Series(shared))['alpha_includes_zero'] is True

    def test_wider_interval_at_higher_confidence(self):
        rng = np.random.default_rng(42)
        port = pd.Series(rng.normal(0.01, 0.03, 36))
        bench = pd.Series(rng.normal(0.005, 0.025, 36))
        w95 = np.diff(bootstrap_confidence_intervals(port, bench, ci=0.95)['sharpe_ci'])[0]
        w99 = np.diff(bootstrap_confidence_intervals(port, bench, ci=0.99)['sharpe_ci'])[0]
        assert w99 >= w95


class TestRegimeConditionalPerformance:
    def test_groups_compound_and_count(self):
        periods = [
            {'period_start': '2025-01-01', 'period_end': '2025-01-31', 'port_return': 10.0, 'bench_return': 5.0, 'alpha': 5.0, 'regime': 'risk_on'},
            {'period_start': '2025-02-01', 'period_end': '2025-02-28', 'port_return': -5.0, 'bench_return': -2.0, 'alpha': -3.0, 'regime': 'risk_on'},
            {'period_start': '2025-03-01', 'period_end': '2025-03-31', 'port_return': 2.0, 'bench_return': 1.0, 'alpha': 1.0, 'regime': 'crisis'},
        ]
        out = regime_conditional_performance({'periods': periods})
        assert set(out) == {'risk_on', 'crisis'}
        risk_on = out['risk_on']
        assert set(risk_on) == {'n_months', 'total_return', 'benchmark_return', 'alpha', 'win_rate'}
        assert risk_on['n_months'] == 2
        assert risk_on['total_return'] == pytest.approx((1.1 * 0.95 - 1) * 100, abs=0.011)
        assert risk_on['benchmark_return'] == pytest.approx((1.05 * 0.98 - 1) * 100, abs=0.011)
        assert risk_on['alpha'] == pytest.approx(risk_on['total_return'] - risk_on['benchmark_return'], abs=0.011)
        assert risk_on['win_rate'] == 50.0
        assert out['crisis'] == {'n_months': 1, 'total_return': 2.0, 'benchmark_return': 1.0, 'alpha': 1.0, 'win_rate': 100.0}

    def test_empty_inputs(self):
        assert regime_conditional_performance(None) == {}
        assert regime_conditional_performance({'periods': []}) == {}
        assert regime_conditional_performance({}) == {}
