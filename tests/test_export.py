import json
import os
from datetime import datetime, timedelta
from unittest.mock import MagicMock

import pytest
import pytz

import quantshield.live.export as de

IST = pytz.timezone('Asia/Kolkata')

STATE = {
    'holdings': {'NIFTYBEES.NS': 9, 'SBIN.NS': 1, 'BAJFINANCE.NS': 1},
    'cash': 416.35,
    'avg_cost': {'NIFTYBEES.NS': 275.75, 'SBIN.NS': 1047.1, 'BAJFINANCE.NS': 1054.8},
    'updated': '2026-07-20T04:51:15',
}
QUOTES = {'NIFTYBEES.NS': 275.20, 'SBIN.NS': 1056.10, 'BAJFINANCE.NS': 1071.90}
TRACK = {
    'inception': {'date': '2026-07-20', 'capital': 5005.09, 'units': 18.104211},
    'snapshots': [
        {'date': '2026-07-20', 'portfolio_value': 5005.09, 'cash': 416.35, 'niftybees_benchmark_value': 5005.09},
        {'date': '2026-07-21', 'portfolio_value': 5060.00, 'cash': 416.35, 'niftybees_benchmark_value': 5030.00},
        {'date': '2026-07-22', 'portfolio_value': 4990.00, 'cash': 416.35, 'niftybees_benchmark_value': 5010.00},
    ],
}
FORBIDDEN = {'cash', 'avg_cost', 'cost', 'value', 'value_now', 'nav', 'pnl', 'day_pnl', 'total_pnl',
             'inception_capital', 'capital', 'turnover_today', 'auto_execute', 'live_mode',
             'zerodha_token_fresh', 'kill_switch', 'scores', 'target_portfolio', 'journal', 'fills', 'qty', 'price',
             'holdings', 'units', 'portfolio_value', 'order_id', 'user_id', 'client_id', 'api_key', 'access_token',
             'limit_px', 'fill_px', 'est_cost', 'plan_ref_price'}


def now_ist(y: int = 2026, m: int = 7, d: int = 23, hh: int = 11, mm: int = 0) -> datetime:
    return IST.localize(datetime(y, m, d, hh, mm))


def walk(obj: object, path: str = '') -> list[tuple[str, object]]:
    out = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            out.append((f'{path}.{k}', k))
            out.extend(walk(v, f'{path}.{k}'))
    elif isinstance(obj, list):
        for v in obj:
            out.extend(walk(v, path))
    return out


class TestPositions:
    def test_weights_from_live_quotes(self) -> None:
        positions, total = de.build_positions(STATE, QUOTES)
        assert total == pytest.approx(416.35 + 9 * 275.20 + 1056.10 + 1071.90, abs=0.01)
        assert [p['symbol'] for p in positions] == ['NIFTYBEES', 'BAJFINANCE', 'SBIN']
        assert set(positions[0]) == {'symbol', 'weight_pct'}
        assert sum(p['weight_pct'] for p in positions) == pytest.approx(100 - 416.35 / total * 100, abs=0.2)

    def test_no_quotes_gives_no_value(self) -> None:
        positions, total = de.build_positions(STATE, None)
        assert total is None
        assert len(positions) == 3
        assert all(0 < p['weight_pct'] < 100 for p in positions)

    def test_partial_quotes_fall_back_per_symbol(self) -> None:
        positions, total = de.build_positions(STATE, {'SBIN.NS': 1056.10})
        assert total == pytest.approx(416.35 + 9 * 275.75 + 1056.10 + 1054.8, abs=0.01)


class TestCurve:
    def test_indexed_to_100_at_inception(self) -> None:
        curve = de.indexed_curve(TRACK, None, None, '2026-07-23')
        assert curve[0] == {'date': '2026-07-20', 'portfolio': 100.0, 'benchmark': 100.0}
        assert curve[1]['portfolio'] == pytest.approx(5060.0 / 5005.09 * 100, abs=0.001)
        assert curve[1]['benchmark'] == pytest.approx(5030.0 / 5005.09 * 100, abs=0.001)
        assert len(curve) == 3

    def test_live_value_appends_intraday_point(self) -> None:
        curve = de.indexed_curve(TRACK, 5100.0, 5050.0, '2026-07-23')
        assert len(curve) == 4
        assert curve[-1]['date'] == '2026-07-23'
        assert curve[-1]['portfolio'] == pytest.approx(5100.0 / 5005.09 * 100, abs=0.001)
        assert curve[-1]['benchmark'] == pytest.approx(5050.0 / 5005.09 * 100, abs=0.001)

    def test_live_value_overwrites_todays_snapshot(self) -> None:
        curve = de.indexed_curve(TRACK, 5100.0, None, '2026-07-22')
        assert len(curve) == 3
        assert curve[-1]['portfolio'] == pytest.approx(5100.0 / 5005.09 * 100, abs=0.001)
        assert curve[-1]['benchmark'] == pytest.approx(5010.0 / 5005.09 * 100, abs=0.001)

    def test_no_quotes_never_touches_curve(self) -> None:
        assert de.indexed_curve(TRACK, None, None, '2026-07-22') == de.indexed_curve(TRACK, None, 9999.0, '2026-07-23')

    def test_empty_track(self) -> None:
        assert de.indexed_curve({'snapshots': []}, 5000.0, None, '2026-07-23') == []

    def test_drawdown_tracks_peak(self) -> None:
        dd = de.drawdown_series(de.indexed_curve(TRACK, None, None, '2026-07-23'))
        assert [d['dd_pct'] for d in dd[:2]] == [0.0, 0.0]
        assert dd[2]['dd_pct'] == pytest.approx((4990.0 / 5060.0 - 1) * 100, abs=0.01)


class TestMetrics:
    def test_returns_alpha_drawdown_and_day_change(self) -> None:
        curve = de.indexed_curve(TRACK, 5100.0, 5050.0, '2026-07-23')
        m = de.build_metrics(curve, TRACK, 5100.0, '2026-07-23')
        assert m['total_return_pct'] == pytest.approx((5100.0 / 5005.09 - 1) * 100, abs=0.01)
        assert m['bench_return_pct'] == pytest.approx((5050.0 / 5005.09 - 1) * 100, abs=0.01)
        assert m['alpha_pct'] == pytest.approx(m['total_return_pct'] - m['bench_return_pct'], abs=0.011)
        assert m['max_drawdown_pct'] == pytest.approx((4990.0 / 5060.0 - 1) * 100, abs=0.01)
        assert m['day_change_pct'] == pytest.approx((5100.0 / 4990.0 - 1) * 100, abs=0.01)

    def test_no_quotes_means_no_day_change(self) -> None:
        curve = de.indexed_curve(TRACK, None, None, '2026-07-23')
        m = de.build_metrics(curve, TRACK, None, '2026-07-23')
        assert m['day_change_pct'] is None
        assert m['total_return_pct'] == pytest.approx((4990.0 / 5005.09 - 1) * 100, abs=0.01)

    def test_empty_curve(self) -> None:
        m = de.build_metrics([], {}, None, '2026-07-23')
        assert m == {'total_return_pct': 0.0, 'bench_return_pct': 0.0, 'alpha_pct': 0.0,
                     'max_drawdown_pct': 0.0, 'day_change_pct': None}


class TestExecution:
    def test_counters_and_guardrails_from_executor(self) -> None:
        import quantshield.live.executor as ee
        journal = [
            {'date': '2026-07-21', 'symbol': 'SBIN.NS', 'order_id': 'X1', 'status': 'COMPLETE'},
            {'date': '2026-07-21', 'symbol': 'LT.NS', 'order_id': None, 'status': 'SKIPPED_GUARDRAIL'},
            {'date': '2026-07-20', 'symbol': 'NIFTYBEES.NS', 'order_id': 'X0', 'status': 'COMPLETE'},
        ]
        fills = [{'slippage_bps': 3.0, 'est_cost': 1.2}, {'slippage_bps': -2.0, 'est_cost': 0.9}, {'slippage_bps': None}]
        ex = de.build_execution(journal, fills, '2026-07-21')
        assert ex == {
            'total_fills': 3, 'avg_slippage_bps': 0.5, 'orders_today': 1,
            'guardrails': {'max_order_value': ee.MAX_ORDER_VALUE, 'max_day_turnover': ee.MAX_DAY_TURNOVER,
                           'max_orders_per_day': ee.MAX_ORDERS_PER_DAY, 'limit_band_pct': 1.0,
                           'max_plan_age_h': ee.MAX_PLAN_AGE_H, 'order_type': 'LIMIT', 'product': 'CNC'},
        }
        assert ex['guardrails']['max_order_value'] == 3000 and ex['guardrails']['max_day_turnover'] == 6000
        assert ex['guardrails']['max_orders_per_day'] == 6 and ex['guardrails']['max_plan_age_h'] == 6

    def test_no_fills(self) -> None:
        assert de.build_execution([], [], '2026-07-21')['avg_slippage_bps'] is None


class TestMonitor:
    @pytest.fixture
    def paths(self, tmp_path: object, monkeypatch: pytest.MonkeyPatch) -> object:
        monkeypatch.setattr(de, 'HEARTBEAT_PATH', str(tmp_path / 'hb.json'))
        monkeypatch.setattr(de, 'KILL_PATH', str(tmp_path / 'KILL'))
        return tmp_path

    def test_halted_when_kill_file(self, paths: object) -> None:
        (paths / 'KILL').write_text('stop')
        mon = de.build_monitor(now_ist(), {'generated': '2026-07-23T09:30:00'})
        assert mon == {'heartbeat_age_min': None, 'loop_status': 'halted', 'last_plan_date': '2026-07-23'}

    def test_active_when_plan_is_today(self, paths: object) -> None:
        assert de.build_monitor(now_ist(), {'generated': '2026-07-23T09:30:00'})['loop_status'] == 'active'

    def test_active_when_heartbeat_recent(self, paths: object) -> None:
        now = now_ist()
        (paths / 'hb.json').write_text(json.dumps({'timestamp': (now - timedelta(minutes=20)).isoformat()}))
        mon = de.build_monitor(now, {'generated': '2026-07-01T09:30:00'})
        assert mon['loop_status'] == 'active' and mon['heartbeat_age_min'] == 20
        assert mon['last_plan_date'] == '2026-07-01'

    def test_idle_when_stale(self, paths: object) -> None:
        now = now_ist()
        (paths / 'hb.json').write_text(json.dumps({'timestamp': (now - timedelta(hours=3)).isoformat()}))
        mon = de.build_monitor(now, {})
        assert mon == {'heartbeat_age_min': 180, 'loop_status': 'idle', 'last_plan_date': None}


class TestQuotes:
    def test_quotes_from_holdings_only(self, monkeypatch: pytest.MonkeyPatch) -> None:
        kite = MagicMock()
        kite.holdings.return_value = [
            {'tradingsymbol': 'NIFTYBEES', 'last_price': 275.2, 'close_price': 275.6},
            {'tradingsymbol': 'SBIN', 'last_price': 0},
            {'tradingsymbol': 'UNRELATED', 'last_price': 10.0},
        ]
        monkeypatch.setattr(de, 'get_kite', lambda: kite)
        assert de.fetch_quotes(['NIFTYBEES.NS', 'SBIN.NS']) == {'NIFTYBEES.NS': 275.2}

    def test_no_token_returns_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(de, 'get_kite', lambda: None)
        assert de.fetch_quotes(['NIFTYBEES.NS']) is None

    def test_broker_error_returns_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        kite = MagicMock()
        kite.holdings.side_effect = RuntimeError('down')
        monkeypatch.setattr(de, 'get_kite', lambda: kite)
        assert de.fetch_quotes(['NIFTYBEES.NS']) is None


class TestPayloadContract:
    @pytest.fixture
    def plan(self) -> dict:
        return {'generated': '2026-07-23T09:30:00', 'regime': 'risk_on', 'capital': 5017.64,
                'orders': [{'action': 'BUY', 'symbol': 'LT.NS', 'qty': 1}], 'warnings': ['w1', 'w2'],
                'scores': {'SBIN.NS': 0.66}, 'target_portfolio': {'SBIN.NS': 1}}

    def test_shape_with_live_quotes(self, plan: dict, monkeypatch: pytest.MonkeyPatch, tmp_path: object) -> None:
        monkeypatch.setattr(de, 'HEARTBEAT_PATH', str(tmp_path / 'hb.json'))
        monkeypatch.setattr(de, 'KILL_PATH', str(tmp_path / 'KILL'))
        payload = de.build_payload(now_ist(), STATE, plan, TRACK, [], [], QUOTES)
        assert set(payload) == {'generated', 'quotes_live', 'account', 'metrics', 'series', 'execution', 'plan', 'monitor'}
        assert payload['quotes_live'] is True
        assert payload['account'] == {
            'broker': 'Zerodha', 'product': 'CNC delivery', 'inception_date': '2026-07-20', 'days_live': 4,
            'positions': payload['account']['positions'],
        }
        assert set(payload['metrics']) == {'total_return_pct', 'bench_return_pct', 'alpha_pct', 'max_drawdown_pct', 'day_change_pct'}
        assert set(payload['series']) == {'equity_curve', 'drawdown'}
        assert payload['series']['equity_curve'][0]['portfolio'] == 100.0
        assert payload['series']['equity_curve'][-1]['date'] == '2026-07-23'
        assert payload['plan'] == {'generated': '2026-07-23T09:30:00', 'regime': 'risk_on', 'orders': 1, 'warnings': 2}
        assert set(payload['execution']) == {'total_fills', 'avg_slippage_bps', 'orders_today', 'guardrails'}
        assert payload['monitor']['loop_status'] == 'active'
        assert payload['metrics']['day_change_pct'] is not None

    def test_no_quotes_uses_last_snapshot_and_no_day_pnl(self, plan: dict, monkeypatch: pytest.MonkeyPatch, tmp_path: object) -> None:
        monkeypatch.setattr(de, 'HEARTBEAT_PATH', str(tmp_path / 'hb.json'))
        monkeypatch.setattr(de, 'KILL_PATH', str(tmp_path / 'KILL'))
        payload = de.build_payload(now_ist(), STATE, plan, TRACK, [], [], None)
        assert payload['quotes_live'] is False
        assert payload['series']['equity_curve'][-1]['date'] == '2026-07-22'
        assert len(payload['series']['equity_curve']) == 3
        assert payload['metrics']['day_change_pct'] is None
        assert payload['metrics']['total_return_pct'] == pytest.approx((4990.0 / 5005.09 - 1) * 100, abs=0.01)

    def test_no_private_fields_anywhere(self, plan: dict, monkeypatch: pytest.MonkeyPatch, tmp_path: object) -> None:
        monkeypatch.setattr(de, 'HEARTBEAT_PATH', str(tmp_path / 'hb.json'))
        monkeypatch.setattr(de, 'KILL_PATH', str(tmp_path / 'KILL'))
        monkeypatch.setenv('AUTO_EXECUTE', 'true')
        for quotes in (QUOTES, None):
            payload = de.build_payload(now_ist(), STATE, plan, TRACK, [{'date': '2026-07-23', 'order_id': 'X', 'qty': 1, 'limit_px': 1000.0}],
                                       [{'slippage_bps': 1.0, 'est_cost': 1.0, 'fill_px': 1000.0}], quotes)
            keys = {k for _, k in walk(payload)}
            assert not keys & FORBIDDEN, keys & FORBIDDEN
            text = json.dumps(payload)
            for needle in ('416.35', '275.75', '1047.1', '1054.8', '5005.09', '18.104211', 'AUTO_EXECUTE', 'token', 'Rs.', '"X"'):
                assert needle not in text, needle
            for needle in ('"symbol": "NIFTYBEES"', '"weight_pct"'):
                assert needle in text, needle

    def test_empty_inputs(self, monkeypatch: pytest.MonkeyPatch, tmp_path: object) -> None:
        monkeypatch.setattr(de, 'HEARTBEAT_PATH', str(tmp_path / 'hb.json'))
        monkeypatch.setattr(de, 'KILL_PATH', str(tmp_path / 'KILL'))
        payload = de.build_payload(now_ist(), {}, {}, {'inception': {}, 'snapshots': []}, [], [], None)
        assert payload['account']['days_live'] == 0 and payload['account']['positions'] == []
        assert payload['series'] == {'equity_curve': [], 'drawdown': []}
        assert payload['monitor'] == {'heartbeat_age_min': None, 'loop_status': 'idle', 'last_plan_date': None}


def test_main_writes_payload_read_only(tmp_path: object, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture) -> None:
    files = {
        'STATE_PATH': ('state.json', STATE), 'PLAN_PATH': ('plan.json', {'generated': '2026-07-23T09:30:00', 'orders': []}),
        'TRACK_PATH': ('track.json', TRACK), 'JOURNAL_PATH': ('journal.json', []),
    }
    for name, (fname, data) in files.items():
        (tmp_path / fname).write_text(json.dumps(data))
        monkeypatch.setattr(de, name, str(tmp_path / fname))
    monkeypatch.setattr(de, 'TRADE_LOG_PATH', str(tmp_path / 'trades.jsonl'))
    monkeypatch.setattr(de, 'HEARTBEAT_PATH', str(tmp_path / 'hb.json'))
    monkeypatch.setattr(de, 'KILL_PATH', str(tmp_path / 'KILL'))
    out = tmp_path / 'out' / 'dashboard.json'
    monkeypatch.setattr(de, 'OUT_PATH', str(out))
    monkeypatch.setattr(de, 'fetch_quotes', lambda syms: QUOTES)
    before = {f: os.path.getmtime(tmp_path / f) for f in ('state.json', 'plan.json', 'track.json', 'journal.json')}
    de.main()
    payload = json.loads(out.read_text())
    assert payload['quotes_live'] is True
    assert payload['account']['broker'] == 'Zerodha'
    assert {f: os.path.getmtime(tmp_path / f) for f in before} == before
    stdout = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert stdout['ok'] is True and set(stdout) == {'ok', 'quotes_live', 'generated'}
