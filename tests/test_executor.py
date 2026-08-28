import json
import os
import sys
from datetime import timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import quantshield.live.executor as ee


def today_ist():
    return ee.now_ist().strftime('%Y-%m-%d')


def fresh_plan(orders):
    return {
        'generated': ee.now_ist().isoformat(),
        'regime': 'risk_on',
        'orders': orders,
    }


def buy(sym, qty, ref):
    return {'action': 'BUY', 'symbol': sym, 'qty': qty, 'ref_price': ref}


def sell(sym, qty, ref):
    return {'action': 'SELL', 'symbol': sym, 'qty': qty, 'ref_price': ref}


DEFAULT_STATE = {
    'holdings': {'NIFTYBEES.NS': 9, 'SBIN.NS': 1, 'BAJFINANCE.NS': 1},
    'cash': 416.35,
    'avg_cost': {'NIFTYBEES.NS': 275.75, 'SBIN.NS': 1047.1, 'BAJFINANCE.NS': 1054.8},
}

BROKER_HOLDINGS = [
    {'tradingsymbol': 'NIFTYBEES', 'quantity': 9, 't1_quantity': 0, 'average_price': 275.75},
    {'tradingsymbol': 'SBIN', 'quantity': 1, 't1_quantity': 0, 'average_price': 1047.1},
    {'tradingsymbol': 'BAJFINANCE', 'quantity': 1, 't1_quantity': 0, 'average_price': 1054.8},
]


@pytest.fixture
def env(tmp_path, monkeypatch):
    pdir = tmp_path / 'portfolio'
    pdir.mkdir()
    monkeypatch.setattr(ee, 'PLAN_PATH', str(pdir / 'plan.json'))
    monkeypatch.setattr(ee, 'STATE_PATH', str(pdir / 'state.json'))
    monkeypatch.setattr(ee, 'JOURNAL_PATH', str(pdir / 'journal.json'))
    monkeypatch.setattr(ee, 'TRADE_LOG_PATH', str(tmp_path / 'journal' / 'trade_log.jsonl'))
    monkeypatch.setattr(ee, 'KILL_FILE', str(tmp_path / 'KILL'))
    monkeypatch.setattr(ee, 'LOCK_PATH', str(pdir / '.execute.lock'))
    monkeypatch.setenv('AUTO_EXECUTE', 'true')
    monkeypatch.setenv('ZERODHA_LIVE_MODE', 'true')
    notify_mock = MagicMock()
    monkeypatch.setattr(ee, 'notify', notify_mock)
    monkeypatch.setattr(ee.time, 'sleep', lambda s: None)
    with open(ee.STATE_PATH, 'w') as f:
        json.dump(DEFAULT_STATE, f)

    class Env:
        pass

    e = Env()
    e.tmp = tmp_path
    e.notify = notify_mock
    e.kite = MagicMock()
    e.kite.holdings.return_value = BROKER_HOLDINGS
    e.kite.positions.return_value = {'net': []}
    e.kite.margins.return_value = {'available': {'live_balance': 100000.0}}
    e.kite.place_order.return_value = 'OID-1'
    e.kite.orders.return_value = []
    monkeypatch.setattr(ee, 'get_kite', lambda: e.kite)

    def write_plan(plan):
        with open(ee.PLAN_PATH, 'w') as f:
            json.dump(plan, f)

    def write_journal(entries):
        with open(ee.JOURNAL_PATH, 'w') as f:
            json.dump(entries, f)

    def read_journal():
        with open(ee.JOURNAL_PATH) as f:
            return json.load(f)

    def read_state():
        with open(ee.STATE_PATH) as f:
            return json.load(f)

    e.write_plan = write_plan
    e.write_journal = write_journal
    e.read_journal = read_journal
    e.read_state = read_state
    return e


def run_main(argv=None):
    with patch.object(sys, 'argv', ['quantshield.live.executor.py'] + (argv or [])):
        with pytest.raises(SystemExit) as exc:
            ee.main()
    return exc.value.code or 0


class TestLimitPrice:
    def test_buy_band_exact_tick(self):
        assert ee.limit_price(100.0, 'BUY', 0.01) == 101.0

    def test_sell_band_exact_tick(self):
        assert ee.limit_price(100.0, 'SELL', 0.01) == 99.0

    def test_buy_rounds_up_to_tick(self):
        assert ee.limit_price(103.33, 'BUY', 0.01) == 104.40

    def test_sell_rounds_down_to_tick(self):
        assert ee.limit_price(103.33, 'SELL', 0.01) == 102.25

    def test_double_band_for_modify(self):
        assert ee.limit_price(100.0, 'BUY', 2 * ee.LIMIT_BAND) == 102.0

    @pytest.mark.parametrize('ref,action,expected', [
        (1003.33, 'BUY', 1013.40), (1003.33, 'SELL', 993.25),
        (275.75, 'BUY', 278.55), (275.75, 'SELL', 272.95),
        (99.99, 'BUY', 101.00), (99.99, 'SELL', 98.95),
        (0.07, 'BUY', 0.10), (0.07, 'SELL', 0.05),
    ])
    def test_hand_computed_tick_rounding(self, ref: float, action: str, expected: float) -> None:
        px = ee.limit_price(ref, action, ee.LIMIT_BAND)
        assert px == expected
        assert round(px / ee.TICK) == pytest.approx(px / ee.TICK, abs=1e-9)
        assert ee.TICK == 0.05 and ee.LIMIT_BAND == 0.01
        if action == 'BUY':
            assert px >= ref * 1.01 - 1e-9
            assert px - ref * 1.01 < ee.TICK
        else:
            assert px <= ref * 0.99 + 1e-9
            assert ref * 0.99 - px < ee.TICK


class TestZsym:
    def test_strips_ns(self):
        assert ee.zsym('NIFTYBEES.NS') == 'NIFTYBEES'

    def test_leaves_bare(self):
        assert ee.zsym('SBIN') == 'SBIN'


class TestPlanFreshness:
    def test_yesterday_plan_refused(self, env, capsys):
        plan = fresh_plan([buy('SBIN.NS', 1, 1000.0)])
        plan['generated'] = (ee.now_ist() - timedelta(days=1)).isoformat()
        env.write_plan(plan)
        assert run_main() == 0
        assert 'no plan generated today' in capsys.readouterr().err
        env.kite.place_order.assert_not_called()

    def test_stale_same_day_plan_refused(self, env, monkeypatch, capsys):
        plan = fresh_plan([buy('SBIN.NS', 1, 1000.0)])
        plan['generated'] = (ee.now_ist() - timedelta(seconds=5)).isoformat()
        monkeypatch.setattr(ee, 'MAX_PLAN_AGE_H', 0)
        env.write_plan(plan)
        assert run_main() == 0
        assert 'refusing' in capsys.readouterr().err
        env.kite.place_order.assert_not_called()
        assert env.notify.called

    def test_missing_plan_exits_zero(self, env):
        assert run_main() == 0
        env.kite.place_order.assert_not_called()

    def test_empty_orders_nothing_to_do(self, env, capsys):
        env.write_plan(fresh_plan([]))
        assert run_main() == 0
        assert 'nothing to do' in capsys.readouterr().err
        env.kite.place_order.assert_not_called()


class TestKillSwitch:
    def test_kill_file_halts_before_any_order(self, env, capsys):
        env.write_plan(fresh_plan([buy('SBIN.NS', 1, 1000.0)]))
        with open(ee.KILL_FILE, 'w') as f:
            f.write('stop')
        assert run_main() == 2
        env.kite.place_order.assert_not_called()
        env.kite.holdings.assert_not_called()
        assert any('KILL' in str(c) for c in env.notify.call_args_list)


class TestAuth:
    def test_no_token_exits_3(self, env, monkeypatch):
        env.write_plan(fresh_plan([buy('SBIN.NS', 1, 1000.0)]))
        monkeypatch.setattr(ee, 'get_kite', lambda: None)
        assert run_main() == 3
        assert any('login' in str(c).lower() for c in env.notify.call_args_list)
        env.kite.holdings.assert_not_called()

    def test_stale_token_message_names_login_deadline(self, env, monkeypatch):
        env.write_plan(fresh_plan([buy('SBIN.NS', 1, 1000.0)]))
        monkeypatch.setattr(ee, 'get_kite', lambda: None)
        assert run_main() == 3
        sent = env.notify.call_args[0][0]
        assert sent == 'Zerodha access token expired; run the daily login before 09:25 IST'

    def test_real_get_kite_is_zerodha_helper(self, env, monkeypatch, tmp_path):
        import quantshield.broker.zerodha as z
        monkeypatch.setattr(z, 'ACCESS_TOKEN_PATH', str(tmp_path / 'tok.json'))
        monkeypatch.setenv('KITE_API_KEY', 'dummy')
        (tmp_path / 'tok.json').write_text(json.dumps({'access_token': 'x', 'date': '2020-01-01'}))
        monkeypatch.setattr(ee, 'get_kite', z.get_kite)
        env.write_plan(fresh_plan([buy('SBIN.NS', 1, 1000.0)]))
        assert run_main() == 3
        (tmp_path / 'tok.json').write_text(json.dumps({'access_token': 'x', 'date': today_ist()}))
        assert ee.get_kite() is not None

    def test_broker_read_failure_exits_3(self, env):
        env.write_plan(fresh_plan([buy('SBIN.NS', 1, 1000.0)]))
        env.kite.holdings.side_effect = ConnectionError('down')
        assert run_main() == 3
        env.kite.place_order.assert_not_called()


class TestReconcile:
    def test_broker_state_mismatch_aborts(self, env):
        env.write_plan(fresh_plan([sell('SBIN.NS', 1, 1000.0)]))
        env.kite.holdings.return_value = [
            {'tradingsymbol': 'NIFTYBEES', 'quantity': 9, 't1_quantity': 0, 'average_price': 275.75},
        ]
        assert run_main() == 4
        env.kite.place_order.assert_not_called()
        assert any('mismatch' in str(c) for c in env.notify.call_args_list)

    def test_broker_less_than_sell_qty_aborts(self, env):
        state = dict(DEFAULT_STATE, holdings={'SBIN.NS': 5})
        with open(ee.STATE_PATH, 'w') as f:
            json.dump(state, f)
        env.kite.holdings.return_value = [
            {'tradingsymbol': 'SBIN', 'quantity': 5, 't1_quantity': 0, 'average_price': 1000.0},
        ]
        env.write_plan(fresh_plan([sell('SBIN.NS', 6, 1000.0)]))
        assert run_main() == 4
        env.kite.place_order.assert_not_called()

    def test_matching_broker_allows_sell(self, env, monkeypatch):
        env.write_plan(fresh_plan([sell('SBIN.NS', 1, 1000.0)]))
        monkeypatch.setattr(ee, 'wait_fill', lambda k, o, s: ('COMPLETE', 1, 999.0))
        assert run_main() == 0
        assert env.kite.place_order.call_count == 1
        assert env.kite.place_order.call_args.kwargs['transaction_type'] == 'SELL'


class TestGuardrails:
    def test_order_value_cap(self, env):
        env.write_plan(fresh_plan([buy('SBIN.NS', 4, 1000.0)]))
        assert run_main() == 0
        env.kite.place_order.assert_not_called()
        j = env.read_journal()
        assert j[-1]['status'] == 'SKIPPED_GUARDRAIL'

    def test_day_turnover_cap(self, env, monkeypatch):
        env.write_plan(fresh_plan([
            buy('AAA.NS', 1, 2500.0), buy('BBB.NS', 1, 2500.0), buy('CCC.NS', 1, 2500.0),
        ]))
        monkeypatch.setattr(ee, 'wait_fill', lambda k, o, s: ('COMPLETE', 1, 2500.0))
        assert run_main() == 0
        assert env.kite.place_order.call_count == 2
        skipped = [e for e in env.read_journal() if e['status'] == 'SKIPPED_GUARDRAIL']
        assert len(skipped) == 1 and skipped[0]['symbol'] == 'CCC.NS'

    def test_max_orders_per_day(self, env):
        today = today_ist()
        prior = [{'date': today, 'plan_generated': 'other-plan', 'symbol': f'P{i}.NS',
                  'action': 'BUY', 'qty': 1, 'order_id': f'O{i}', 'limit_px': 0.0,
                  'status': 'COMPLETE'} for i in range(ee.MAX_ORDERS_PER_DAY)]
        env.write_journal(prior)
        env.write_plan(fresh_plan([buy('SBIN.NS', 1, 1000.0)]))
        assert run_main() == 0
        env.kite.place_order.assert_not_called()
        assert env.read_journal()[-1]['status'] == 'SKIPPED_GUARDRAIL'

    def test_prior_turnover_counts(self, env):
        today = today_ist()
        env.write_journal([{'date': today, 'plan_generated': 'other-plan', 'symbol': 'P.NS',
                            'action': 'BUY', 'qty': 2, 'order_id': 'O0', 'limit_px': 2500.0,
                            'status': 'COMPLETE'}])
        env.write_plan(fresh_plan([buy('SBIN.NS', 2, 1000.0)]))
        assert run_main() == 0
        env.kite.place_order.assert_not_called()


class TestOrdering:
    def test_sells_execute_before_buys(self, env, monkeypatch):
        env.write_plan(fresh_plan([
            buy('NIFTYBEES.NS', 1, 280.0), sell('SBIN.NS', 1, 1000.0),
        ]))
        monkeypatch.setattr(ee, 'wait_fill', lambda k, o, s: ('COMPLETE', 1, 500.0))
        assert run_main() == 0
        types = [c.kwargs['transaction_type'] for c in env.kite.place_order.call_args_list]
        assert types == ['SELL', 'BUY']

    def test_zerodha_symbol_stripped_and_limit_only(self, env, monkeypatch):
        env.write_plan(fresh_plan([buy('SBIN.NS', 1, 1000.0)]))
        monkeypatch.setattr(ee, 'wait_fill', lambda k, o, s: ('COMPLETE', 1, 1005.0))
        assert run_main() == 0
        kw = env.kite.place_order.call_args.kwargs
        assert kw['tradingsymbol'] == 'SBIN'
        assert kw['order_type'] == 'LIMIT'
        assert kw['product'] == 'CNC'
        assert kw['validity'] == 'DAY'
        assert kw['variety'] == 'regular'
        assert kw['exchange'] == 'NSE'
        assert kw['price'] == ee.limit_price(1000.0, 'BUY', ee.LIMIT_BAND)

    def test_sell_limit_below_ref_rounded_down(self, env, monkeypatch):
        env.write_plan(fresh_plan([sell('SBIN.NS', 1, 1003.33)]))
        monkeypatch.setattr(ee, 'wait_fill', lambda k, o, s: ('COMPLETE', 1, 995.0))
        assert run_main() == 0
        assert env.kite.place_order.call_args.kwargs['price'] == 993.25


class TestIdempotency:
    def test_placing_journaled_before_broker_call(self, env, monkeypatch):
        env.write_plan(fresh_plan([buy('SBIN.NS', 1, 1000.0)]))
        seen = []

        def place(**kwargs):
            seen.append([(e['symbol'], e['status'], e['order_id']) for e in env.read_journal()])
            return 'OID-9'

        env.kite.place_order.side_effect = place
        monkeypatch.setattr(ee, 'wait_fill', lambda k, o, s: ('COMPLETE', 1, 1005.0))
        assert run_main() == 0
        assert seen == [[('SBIN.NS', 'PLACING', None)]]
        assert env.read_journal()[-1]['order_id'] == 'OID-9'

    def test_corrupt_journal_aborts_without_orders(self, env):
        env.write_plan(fresh_plan([buy('SBIN.NS', 1, 1000.0)]))
        with open(ee.JOURNAL_PATH, 'w') as f:
            f.write('{not json')
        assert run_main() == 3
        env.kite.place_order.assert_not_called()
        assert any('unreadable' in str(c) for c in env.notify.call_args_list)

    def test_rerun_places_nothing(self, env, monkeypatch, capsys):
        plan = fresh_plan([buy('SBIN.NS', 1, 1000.0), sell('BAJFINANCE.NS', 1, 1050.0)])
        env.write_plan(plan)
        today = today_ist()
        env.write_journal([
            {'date': today, 'plan_generated': plan['generated'], 'symbol': 'SBIN.NS',
             'action': 'BUY', 'qty': 1, 'order_id': 'A', 'limit_px': 1010.0, 'status': 'COMPLETE'},
            {'date': today, 'plan_generated': plan['generated'], 'symbol': 'BAJFINANCE.NS',
             'action': 'SELL', 'qty': 1, 'order_id': 'B', 'limit_px': 1039.5, 'status': 'PENDING'},
        ])
        assert run_main() == 0
        env.kite.place_order.assert_not_called()
        assert 'nothing to do' in capsys.readouterr().out

    def test_partial_journal_places_remainder(self, env, monkeypatch):
        plan = fresh_plan([buy('SBIN.NS', 1, 1000.0), buy('NIFTYBEES.NS', 1, 280.0)])
        env.write_plan(plan)
        today = today_ist()
        env.write_journal([
            {'date': today, 'plan_generated': plan['generated'], 'symbol': 'SBIN.NS',
             'action': 'BUY', 'qty': 1, 'order_id': 'A', 'limit_px': 1010.0, 'status': 'COMPLETE'},
        ])
        monkeypatch.setattr(ee, 'wait_fill', lambda k, o, s: ('COMPLETE', 1, 282.0))
        assert run_main() == 0
        assert env.kite.place_order.call_count == 1
        assert env.kite.place_order.call_args.kwargs['tradingsymbol'] == 'NIFTYBEES'


class TestUnfilledFlow:
    def test_place_modify_cancel_journals_unfilled(self, env, monkeypatch):
        env.write_plan(fresh_plan([buy('SBIN.NS', 1, 1000.0)]))
        monkeypatch.setattr(ee, 'wait_fill', MagicMock(side_effect=[('OPEN', 0, 0.0), ('OPEN', 0, 0.0), ('CANCELLED', 0, 0.0)]))
        assert run_main() == 0
        assert env.kite.place_order.call_count == 1
        env.kite.modify_order.assert_called_once()
        assert env.kite.modify_order.call_args.kwargs['price'] == ee.limit_price(1000.0, 'BUY', 2 * ee.LIMIT_BAND)
        env.kite.cancel_order.assert_called_once()
        entry = env.read_journal()[-1]
        assert entry['status'] == 'UNFILLED'
        assert entry['limit_px'] == ee.limit_price(1000.0, 'BUY', 2 * ee.LIMIT_BAND)
        assert any('unfilled' in str(c) for c in env.notify.call_args_list)

    def test_fill_after_modify_journals_complete(self, env, monkeypatch):
        env.write_plan(fresh_plan([buy('SBIN.NS', 1, 1000.0)]))
        monkeypatch.setattr(ee, 'wait_fill', MagicMock(side_effect=[('OPEN', 0, 0.0), ('COMPLETE', 1, 1015.0)]))
        assert run_main() == 0
        env.kite.cancel_order.assert_not_called()
        entry = env.read_journal()[-1]
        assert entry['status'] == 'COMPLETE'
        assert entry['filled_qty'] == 1
        assert entry['avg_price'] == 1015.0


class TestStateUpdate:
    def test_state_refreshed_from_broker_truth_with_weighted_avg_cost(self, env, monkeypatch):
        env.write_plan(fresh_plan([buy('NIFTYBEES.NS', 2, 280.0)]))
        post_holdings = BROKER_HOLDINGS
        post_positions = {'net': [{'tradingsymbol': 'NIFTYBEES', 'product': 'CNC',
                                   'day_buy_quantity': 2, 'day_sell_quantity': 0}]}
        env.kite.holdings.side_effect = [BROKER_HOLDINGS, post_holdings]
        env.kite.positions.side_effect = [{'net': []}, post_positions]
        env.kite.margins.side_effect = [
            {'available': {'live_balance': 3000.0}},
            {'available': {'live_balance': 2420.0}},
        ]
        monkeypatch.setattr(ee, 'wait_fill', lambda k, o, s: ('COMPLETE', 2, 280.0))
        assert run_main() == 0
        state = env.read_state()
        assert state['holdings']['NIFTYBEES.NS'] == 11
        assert state['holdings']['SBIN.NS'] == 1
        assert state['cash'] == 2420.0
        expected = round((9 * 275.75 + 2 * 280.0) / 11, 2)
        assert state['avg_cost']['NIFTYBEES.NS'] == expected
        assert state['avg_cost']['SBIN.NS'] == 1047.1

    def test_trade_log_appended_with_slippage(self, env, monkeypatch):
        env.write_plan(fresh_plan([buy('SBIN.NS', 1, 1000.0)]))
        monkeypatch.setattr(ee, 'wait_fill', lambda k, o, s: ('COMPLETE', 1, 1005.0))
        assert run_main() == 0
        with open(ee.TRADE_LOG_PATH) as f:
            recs = [json.loads(line) for line in f]
        assert len(recs) == 1
        assert recs[0]['symbol'] == 'SBIN.NS'
        assert recs[0]['fill_px'] == 1005.0
        assert recs[0]['slippage_bps'] == 50.0
        assert recs[0]['plan_ref_price'] == 1000.0


class TestCashScaling:
    def test_buy_scaled_to_available_cash(self, env, monkeypatch, capsys):
        env.kite.margins.return_value = {'available': {'live_balance': 1100.0}}
        env.write_plan(fresh_plan([buy('SBIN.NS', 2, 1000.0)]))
        monkeypatch.setattr(ee, 'wait_fill', lambda k, o, s: ('COMPLETE', 1, 1008.0))
        assert run_main() == 0
        assert env.kite.place_order.call_args.kwargs['quantity'] == 1
        assert 'scaled 2->1' in capsys.readouterr().out

    def test_buy_unaffordable_skipped(self, env):
        env.kite.margins.return_value = {'available': {'live_balance': 50.0}}
        env.write_plan(fresh_plan([buy('SBIN.NS', 1, 1000.0)]))
        assert run_main() == 0
        env.kite.place_order.assert_not_called()
        assert env.read_journal()[-1]['status'] == 'SKIPPED_CASH'


class TestDryRunAndGating:
    def test_dry_run_flag_places_zero_orders(self, env, capsys):
        env.write_plan(fresh_plan([buy('SBIN.NS', 1, 1000.0), sell('BAJFINANCE.NS', 1, 1050.0)]))
        assert run_main(['--dry-run']) == 0
        env.kite.place_order.assert_not_called()
        env.kite.modify_order.assert_not_called()
        out = capsys.readouterr().out
        assert 'DRY' in out
        assert 'would SELL' in out and 'would BUY' in out
        assert not os.path.exists(ee.JOURNAL_PATH)

    def test_auto_execute_false_forces_dry_run(self, env, monkeypatch, capsys):
        monkeypatch.setenv('AUTO_EXECUTE', 'false')
        env.write_plan(fresh_plan([buy('SBIN.NS', 1, 1000.0)]))
        assert run_main() == 0
        env.kite.place_order.assert_not_called()
        assert 'AUTO_EXECUTE' in capsys.readouterr().err

    def test_live_mode_env_false_forces_dry_run(self, env, monkeypatch):
        monkeypatch.setenv('ZERODHA_LIVE_MODE', 'false')
        env.write_plan(fresh_plan([buy('SBIN.NS', 1, 1000.0)]))
        assert run_main() == 0
        env.kite.place_order.assert_not_called()

    def test_dry_run_notify_suppressed(self, env):
        env.write_plan(fresh_plan([buy('SBIN.NS', 1, 1000.0)]))
        assert run_main(['--dry-run']) == 0
        env.notify.assert_not_called()

    def test_live_mode_sends_report(self, env, monkeypatch):
        env.write_plan(fresh_plan([buy('SBIN.NS', 1, 1000.0)]))
        monkeypatch.setattr(ee, 'wait_fill', lambda k, o, s: ('COMPLETE', 1, 1005.0))
        assert run_main() == 0
        assert any('Execution report' in str(c) for c in env.notify.call_args_list)


class TestPlaceOrderFailure:
    def test_rejected_placement_journaled_and_continues(self, env, monkeypatch):
        env.write_plan(fresh_plan([buy('SBIN.NS', 1, 1000.0), buy('NIFTYBEES.NS', 1, 280.0)]))
        env.kite.place_order.side_effect = [RuntimeError('rms reject'), 'OID-2']
        monkeypatch.setattr(ee, 'wait_fill', lambda k, o, s: ('COMPLETE', 1, 282.0))
        assert run_main() == 0
        statuses = {e['symbol']: e['status'] for e in env.read_journal()}
        assert statuses['SBIN.NS'] == 'FAILED'
        assert statuses['NIFTYBEES.NS'] == 'COMPLETE'

    def test_failed_placement_not_replayed_same_day(self, env, monkeypatch):
        env.write_plan(fresh_plan([buy('SBIN.NS', 1, 1000.0)]))
        env.kite.place_order.side_effect = RuntimeError('rms reject')
        assert run_main() == 0
        assert env.read_journal()[-1]['status'] == 'FAILED'
        env.kite.place_order.reset_mock(side_effect=True)
        assert run_main() == 0
        env.kite.place_order.assert_not_called()

    def test_ambiguous_failure_adopts_live_broker_order(self, env, monkeypatch):
        env.write_plan(fresh_plan([buy('SBIN.NS', 1, 1000.0)]))
        px = ee.limit_price(1000.0, 'BUY', ee.LIMIT_BAND)
        env.kite.place_order.side_effect = ConnectionError('read timeout')
        env.kite.orders.return_value = [{'tradingsymbol': 'SBIN', 'transaction_type': 'BUY',
                                         'quantity': 1, 'price': px, 'status': 'OPEN',
                                         'order_id': 'LIVE-1'}]
        monkeypatch.setattr(ee, 'wait_fill', lambda k, o, s: ('COMPLETE', 1, px))
        assert run_main() == 0
        entry = env.read_journal()[-1]
        assert entry['order_id'] == 'LIVE-1'
        assert entry['status'] == 'COMPLETE'
        assert entry['filled_qty'] == 1


class TestProcessLock:
    def test_second_instance_exits_5(self, env):
        import fcntl
        env.write_plan(fresh_plan([buy('SBIN.NS', 1, 1000.0)]))
        os.makedirs(os.path.dirname(ee.LOCK_PATH), exist_ok=True)
        held = open(ee.LOCK_PATH, 'w')
        fcntl.flock(held, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            assert run_main() == 5
            env.kite.place_order.assert_not_called()
        finally:
            fcntl.flock(held, fcntl.LOCK_UN)
            held.close()


class TestKillMidRun:
    def test_kill_file_mid_loop_halts_remaining_orders(self, env, monkeypatch):
        env.write_plan(fresh_plan([buy('SBIN.NS', 1, 1000.0), buy('NIFTYBEES.NS', 1, 280.0)]))

        def fill_and_kill(k, o, s):
            with open(ee.KILL_FILE, 'w') as f:
                f.write('stop')
            return ('COMPLETE', 1, 1005.0)

        monkeypatch.setattr(ee, 'wait_fill', fill_and_kill)
        assert run_main() == 0
        assert env.kite.place_order.call_count == 1
        assert any('halted mid-run' in str(c) for c in env.notify.call_args_list)


class TestCancelVerification:
    def test_cancel_failure_marks_unverified_and_blocks_rerun(self, env, monkeypatch):
        env.write_plan(fresh_plan([buy('SBIN.NS', 1, 1000.0)]))
        env.kite.cancel_order.side_effect = ConnectionError('blip')
        monkeypatch.setattr(ee, 'wait_fill', MagicMock(
            side_effect=[('OPEN', 0, 0.0), ('OPEN', 0, 0.0), ('OPEN', 0, 0.0)]))
        assert run_main() == 0
        entry = env.read_journal()[-1]
        assert entry['status'] == 'CANCEL_UNVERIFIED'
        assert any('may still be live' in str(c) for c in env.notify.call_args_list)
        env.kite.place_order.reset_mock()
        monkeypatch.setattr(ee, 'wait_fill', MagicMock(return_value=('COMPLETE', 1, 1005.0)))
        assert run_main() == 0
        env.kite.place_order.assert_not_called()

    def test_late_fill_after_cancel_recorded_complete(self, env, monkeypatch):
        env.write_plan(fresh_plan([buy('SBIN.NS', 1, 1000.0)]))
        monkeypatch.setattr(ee, 'wait_fill', MagicMock(
            side_effect=[('OPEN', 0, 0.0), ('OPEN', 0, 0.0), ('COMPLETE', 1, 1012.0)]))
        assert run_main() == 0
        entry = env.read_journal()[-1]
        assert entry['status'] == 'COMPLETE'
        assert entry['filled_qty'] == 1
        with open(ee.TRADE_LOG_PATH) as f:
            recs = [json.loads(line) for line in f]
        assert recs[0]['qty'] == 1 and recs[0]['fill_px'] == 1012.0

    def test_partial_fill_before_cancel_accounted(self, env, monkeypatch):
        env.write_plan(fresh_plan([buy('SBIN.NS', 2, 1000.0)]))
        monkeypatch.setattr(ee, 'wait_fill', MagicMock(
            side_effect=[('OPEN', 0, 0.0), ('OPEN', 1, 1010.0), ('CANCELLED', 1, 1010.0)]))
        assert run_main() == 0
        entry = env.read_journal()[-1]
        assert entry['status'] == 'UNFILLED'
        assert entry['filled_qty'] == 1
        with open(ee.TRADE_LOG_PATH) as f:
            recs = [json.loads(line) for line in f]
        assert recs[0]['qty'] == 1

    def test_nonstandard_open_status_still_modified_and_cancelled(self, env, monkeypatch):
        env.write_plan(fresh_plan([buy('SBIN.NS', 1, 1000.0)]))
        monkeypatch.setattr(ee, 'wait_fill', MagicMock(
            side_effect=[('OPEN PENDING', 0, 0.0), ('TRIGGER PENDING', 0, 0.0), ('CANCELLED', 0, 0.0)]))
        assert run_main() == 0
        env.kite.modify_order.assert_called_once()
        env.kite.cancel_order.assert_called_once()
        assert env.read_journal()[-1]['status'] == 'UNFILLED'


class TestScaledBuyIdempotency:
    def test_scaled_buy_not_replayed_on_rerun(self, env, monkeypatch):
        env.kite.margins.return_value = {'available': {'live_balance': 1100.0}}
        env.write_plan(fresh_plan([buy('SBIN.NS', 2, 1000.0)]))
        monkeypatch.setattr(ee, 'wait_fill', lambda k, o, s: ('COMPLETE', 1, 1008.0))
        assert run_main() == 0
        assert env.kite.place_order.call_count == 1
        env.kite.place_order.reset_mock()
        assert run_main() == 0
        env.kite.place_order.assert_not_called()

    def test_regenerated_plan_same_day_does_not_duplicate(self, env, monkeypatch):
        env.write_plan(fresh_plan([buy('SBIN.NS', 1, 1000.0)]))
        monkeypatch.setattr(ee, 'wait_fill', lambda k, o, s: ('COMPLETE', 1, 1005.0))
        assert run_main() == 0
        assert env.kite.place_order.call_count == 1
        env.write_plan(fresh_plan([buy('SBIN.NS', 1, 1000.0)]))
        env.kite.place_order.reset_mock()
        assert run_main() == 0
        env.kite.place_order.assert_not_called()


class TestStateRefreshSafety:
    def test_non_universe_holdings_excluded_from_state(self, env, monkeypatch):
        post_holdings = BROKER_HOLDINGS + [
            {'tradingsymbol': 'SUZLON', 'quantity': 500, 't1_quantity': 0, 'average_price': 60.0},
        ]
        env.kite.holdings.side_effect = [BROKER_HOLDINGS, post_holdings]
        env.write_plan(fresh_plan([buy('SBIN.NS', 1, 1000.0)]))
        monkeypatch.setattr(ee, 'wait_fill', lambda k, o, s: ('COMPLETE', 1, 1005.0))
        assert run_main() == 0
        state = env.read_state()
        assert 'SUZLON.NS' not in state['holdings']
        assert 'SUZLON.NS' not in state['avg_cost']
        assert state['holdings']['SBIN.NS'] == 1

    def test_state_refresh_failure_exits_6(self, env, monkeypatch):
        env.kite.holdings.side_effect = [BROKER_HOLDINGS, ConnectionError('down')]
        env.write_plan(fresh_plan([buy('SBIN.NS', 1, 1000.0)]))
        monkeypatch.setattr(ee, 'wait_fill', lambda k, o, s: ('COMPLETE', 1, 1005.0))
        assert run_main() == 6
        assert any('state refresh failed' in str(c) for c in env.notify.call_args_list)


class TestTradeLogAppendOnly:
    def test_second_run_appends_and_keeps_prior_lines(self, env, monkeypatch):
        env.write_plan(fresh_plan([buy('SBIN.NS', 1, 1000.0)]))
        monkeypatch.setattr(ee, 'wait_fill', lambda k, o, s: ('COMPLETE', 1, 1005.0))
        assert run_main() == 0
        env.write_plan(fresh_plan([buy('NIFTYBEES.NS', 1, 280.0)]))
        env.kite.place_order.reset_mock()
        assert run_main() == 0
        with open(ee.TRADE_LOG_PATH) as f:
            recs = [json.loads(line) for line in f]
        assert [r['symbol'] for r in recs] == ['SBIN.NS', 'NIFTYBEES.NS']


class TestImportSideEffects:
    def test_import_touches_no_files_and_no_broker(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        import importlib

        import quantshield.broker.zerodha as z
        from quantshield.paths import ROOT
        monkeypatch.chdir(tmp_path)
        calls = []
        monkeypatch.setattr(z, 'get_kite', lambda: calls.append(1))
        monkeypatch.setattr(ee.fcntl, 'flock', lambda *a: calls.append(('flock', a)))
        before = {str(p): p.stat().st_mtime_ns for p in ROOT.rglob('*') if p.is_file()}
        importlib.reload(ee)
        assert calls == []
        assert os.listdir(tmp_path) == []
        assert {str(p): p.stat().st_mtime_ns for p in ROOT.rglob('*') if p.is_file()} == before
        assert not os.path.exists(ee.LOCK_PATH)


class TestExecutionBudget:
    def test_daemon_timeout_covers_worst_case_runtime(self):
        import quantshield.live.daemon as monitor_daemon
        worst = ee.MAX_ORDERS_PER_DAY * (
            ee.POLL_PRIMARY_S + ee.POLL_MODIFIED_S + ee.POLL_CANCEL_S + ee.POLL_STEP_S + ee.ORDER_SLEEP + 10)
        assert monitor_daemon.SMALL_EXECUTE_TIMEOUT > worst
