import json
from datetime import datetime, timedelta

import numpy as np
import pytest

from quantshield.research.track_record import (
    _extract_signals_snapshot,
    _load_track_record,
    append_track_record,
    compute_live_metrics,
    dedupe_by_date,
    generate_monthly_report_data,
    save_monthly_snapshot,
)


@pytest.fixture
def us_output():
    return {
        'market': 'us',
        'regime': {'detected': 'risk_on', 'confidence': 0.85, 'vix': 14.2, 'signal_weights': {}},
        'in_sample': {'port_return': 12.5, 'bench_return': 10.0, 'alpha': 2.5, 'port_sharpe': 1.2,
                      'bench_sharpe': 1.0, 'port_maxdd': -8.0, 'bench_maxdd': -9.0},
        'weights': [
            {'ticker': 'AAPL', 'weight_pct': 15.0, 'price': 180.0, 'momentum': 0.5, 'vol_adj_momentum': 0.3,
             'mean_reversion': -0.1, 'trend': 0.2, 'cross_asset': 0.1, 'composite': 0.35, 'beta': 1.1},
            {'ticker': 'GOOGL', 'weight_pct': 12.0, 'price': 140.0, 'momentum': 0.4, 'vol_adj_momentum': 0.2,
             'mean_reversion': 0.0, 'trend': 0.1, 'cross_asset': 0.15, 'composite': 0.25, 'beta': 1.0},
        ],
        'walk_forward': {'port_return': 30.0, 'periods': [{'x': 1}], 'equity_curve': [{'y': 2}]},
        'correlation': {'avg_30d': 0.45, 'warning': False, 'top_pairs': []},
        'cvar': {'portfolio_cvar': -0.02, 'var': -0.015, 'confidence': 0.95},
    }


@pytest.fixture
def india_output():
    return {
        'market': 'india',
        'regime': {'detected': 'risk_off', 'confidence': 0.6, 'vix': 16.0, 'signal_weights': {}},
        'in_sample': {'port_return': 10.0, 'bench_return': 5.0},
        'weights': [
            {'ticker': 'TCS.NS', 'weight_pct': 10.0, 'price': 3500.0, 'momentum': 0.3, 'vol_adj_momentum': 0.1,
             'mean_reversion': 0.05, 'trend': 0.15, 'cross_asset': 0.05, 'composite': 0.2, 'beta': 0.9},
        ],
    }


def _records(n: int, port_step: float = 1.003, bench_step: float = 1.001, start: str = '2026-04-02') -> list[dict]:
    day0 = datetime.strptime(start, '%Y-%m-%d')
    rows = []
    port, bench = 100000.0, 100000.0
    for i in range(n):
        port *= port_step
        bench *= bench_step
        rows.append({
            'date': (day0 + timedelta(days=i)).strftime('%Y-%m-%d'),
            'combined_value_usd': round(port, 2),
            'us_benchmark_value': round(bench, 2),
            'regime_us': 'risk_on',
            'trades_placed': 1 if i % 30 == 0 else 0,
            'signals_snapshot': {
                'AAPL': {'weight_pct': 15.0, 'composite': 0.3 + i * 0.001},
                'GOOGL': {'weight_pct': 12.0, 'composite': 0.2 - i * 0.001},
            },
        })
    return rows


@pytest.fixture
def synthetic_track_record():
    rng = np.random.default_rng(42)
    rows = _records(60)
    port, bench = 100000.0, 100000.0
    for r in rows:
        port *= 1 + rng.normal(0.001, 0.01)
        bench *= 1 + rng.normal(0.0008, 0.009)
        r['combined_value_usd'] = round(port, 2)
        r['us_benchmark_value'] = round(bench, 2)
    return rows


class TestAppend:
    def test_creates_file_with_us_values(self, tmp_path, us_output):
        path = tmp_path / 'tr.json'
        append_track_record(us_output, None, [], path=path)
        data = json.loads(path.read_text())
        assert len(data) == 1
        rec = data[0]
        assert rec['us_portfolio_value'] == pytest.approx(112500.0)
        assert rec['us_benchmark_value'] == pytest.approx(110000.0)
        assert rec['combined_value_usd'] == rec['us_portfolio_value']
        assert rec['india_portfolio_value'] is None
        assert rec['regime_us'] == 'risk_on'
        assert rec['usdinr'] is None
        assert rec['trades_placed'] == 0

    def test_append_only(self, tmp_path, us_output):
        path = tmp_path / 'tr.json'
        append_track_record(us_output, None, [], path=path)
        append_track_record(us_output, None, [{'ticker': 'AAPL'}], path=path)
        data = json.loads(path.read_text())
        assert len(data) == 2
        assert data[0]['trades_placed'] == 0
        assert data[1]['trades_placed'] == 1
        assert not list(tmp_path.glob('*.tmp'))

    def test_india_combined_with_usdinr(self, tmp_path, us_output, india_output):
        path = tmp_path / 'tr.json'
        append_track_record(us_output, india_output, [], path=path, usdinr=85.0)
        rec = json.loads(path.read_text())[0]
        assert rec['india_portfolio_value'] == pytest.approx(1_100_000.0)
        assert rec['india_benchmark_value'] == pytest.approx(1_050_000.0)
        assert rec['regime_india'] == 'risk_off'
        assert rec['usdinr'] == 85.0
        assert rec['combined_value_usd'] == pytest.approx(112500.0 + 1_100_000.0 / 85.0, abs=0.01)
        assert 'TCS.NS' in rec['signals_snapshot'] and 'AAPL' in rec['signals_snapshot']

    def test_india_without_usdinr_is_not_combined(self, tmp_path, us_output, india_output):
        path = tmp_path / 'tr.json'
        append_track_record(us_output, india_output, [], path=path)
        rec = json.loads(path.read_text())[0]
        assert rec['india_portfolio_value'] == pytest.approx(1_100_000.0)
        assert rec['combined_value_usd'] == pytest.approx(112500.0)
        assert rec['usdinr'] is None

    def test_snapshot_uses_contract_keys(self, us_output):
        snap = _extract_signals_snapshot(us_output)
        assert set(snap) == {'AAPL', 'GOOGL'}
        assert snap['AAPL'] == {
            'momentum': 0.5, 'vol_adj_momentum': 0.3, 'mean_reversion': -0.1, 'trend': 0.2,
            'cross_asset': 0.1, 'composite': 0.35, 'weight_pct': 15.0,
        }


class TestSnapshot:
    def test_monthly_snapshot_fields(self, tmp_path, us_output):
        path = save_monthly_snapshot(us_output, 'us', snapshots_dir=tmp_path)
        assert path.endswith('-us.json')
        snap = json.loads(open(path).read())
        assert set(snap) == {'timestamp', 'market', 'positions', 'regime', 'in_sample', 'walk_forward', 'correlation', 'cvar'}
        assert snap['market'] == 'us'
        assert len(snap['positions']) == 2
        assert snap['walk_forward'] == {'port_return': 30.0}
        assert snap['cvar']['confidence'] == 0.95

    def test_monthly_snapshot_without_walk_forward(self, tmp_path, india_output):
        path = save_monthly_snapshot(india_output, 'india', snapshots_dir=tmp_path)
        snap = json.loads(open(path).read())
        assert snap['walk_forward'] == {}
        assert snap['market'] == 'india'


class TestLiveMetrics:
    def test_insufficient_data(self):
        assert compute_live_metrics([]) == {
            'live_sharpe': None, 'live_alpha_annualized': None, 'live_max_drawdown': None,
            'live_volatility': None, 'current_drawdown': None, 'days_since_inception': 0,
        }
        single = compute_live_metrics(_records(1))
        assert single['live_sharpe'] is None and single['days_since_inception'] == 1

    def test_same_day_duplicates_collapse_to_one_record(self):
        rows = _records(3)
        duplicated = rows + [dict(rows[-1], combined_value_usd=1.0)]
        assert compute_live_metrics(duplicated + rows[-1:])['days_since_inception'] == 2
        deduped = dedupe_by_date(duplicated + rows[-1:])
        assert [r['date'] for r in deduped] == [r['date'] for r in rows]
        assert deduped[-1]['combined_value_usd'] == rows[-1]['combined_value_usd']

    def test_metrics_with_data(self, synthetic_track_record):
        res = compute_live_metrics(synthetic_track_record)
        assert set(res) == {'live_sharpe', 'live_alpha_annualized', 'live_max_drawdown',
                            'live_volatility', 'current_drawdown', 'days_since_inception'}
        assert isinstance(res['live_sharpe'], float)
        assert res['live_max_drawdown'] <= 0
        assert res['live_volatility'] > 0
        assert res['days_since_inception'] == 59

    def test_drawdown_calculation(self):
        rows = [
            {'date': '2026-04-02', 'combined_value_usd': 100000, 'us_benchmark_value': 100000},
            {'date': '2026-04-03', 'combined_value_usd': 110000, 'us_benchmark_value': 105000},
            {'date': '2026-04-04', 'combined_value_usd': 99000, 'us_benchmark_value': 103000},
            {'date': '2026-04-05', 'combined_value_usd': 105000, 'us_benchmark_value': 104000},
        ]
        res = compute_live_metrics(rows)
        assert res['live_max_drawdown'] == pytest.approx(-10.0, abs=0.01)
        assert res['current_drawdown'] == pytest.approx((105000 / 110000 - 1) * 100, abs=0.01)

    def test_alpha_sign(self):
        assert compute_live_metrics(_records(30, 1.003, 1.001))['live_alpha_annualized'] > 0
        assert compute_live_metrics(_records(30, 0.999, 1.001))['live_alpha_annualized'] < 0

    def test_dedupe_keeps_last_and_sorts(self):
        rows = [
            {'date': '2026-04-03', 'combined_value_usd': 2},
            {'date': '2026-04-02', 'combined_value_usd': 1},
            {'date': '2026-04-03', 'combined_value_usd': 3},
        ]
        assert dedupe_by_date(rows) == [
            {'date': '2026-04-02', 'combined_value_usd': 1},
            {'date': '2026-04-03', 'combined_value_usd': 3},
        ]


class TestMonthlyReport:
    def test_empty_and_missing_month(self, synthetic_track_record):
        empty = generate_monthly_report_data([], '2026-04')
        assert empty['monthly_return'] is None and empty['num_trades'] == 0
        assert generate_monthly_report_data(synthetic_track_record, '2025-01')['monthly_return'] is None

    def test_month_with_data(self, synthetic_track_record):
        res = generate_monthly_report_data(synthetic_track_record, '2026-04')
        assert res['month'] == '2026-04'
        april = [r for r in synthetic_track_record if r['date'].startswith('2026-04')]
        expected = (april[-1]['combined_value_usd'] / april[0]['combined_value_usd'] - 1) * 100
        assert res['monthly_return'] == pytest.approx(expected, abs=1e-3)
        assert res['benchmark_return'] is not None
        assert res['cumulative_return'] == pytest.approx(
            (april[-1]['combined_value_usd'] / synthetic_track_record[0]['combined_value_usd'] - 1) * 100, abs=1e-3)
        assert res['regime_summary'] == {'risk_on': len(april)}
        assert res['num_trades'] == 1

    def test_contributors_ranked(self, synthetic_track_record):
        res = generate_monthly_report_data(synthetic_track_record, '2026-04')
        assert res['top_contributors'][0]['ticker'] == 'AAPL'
        assert res['bottom_contributors'][-1]['ticker'] == 'GOOGL'
        assert res['top_contributors'][0]['contribution'] > 0 > res['bottom_contributors'][-1]['contribution']


def test_load_track_record(tmp_path):
    missing = tmp_path / 'missing.json'
    assert _load_track_record(missing) == []
    existing = tmp_path / 'existing.json'
    existing.write_text(json.dumps([{'date': '2026-04-02'}]))
    assert _load_track_record(existing) == [{'date': '2026-04-02'}]
