import json
import os
import subprocess
import sys
from unittest.mock import MagicMock, patch

import pytest

import quantshield.broker.alpaca as a


@pytest.fixture(autouse=True)
def isolated_paths(tmp_path, monkeypatch):
    monkeypatch.setattr(a, 'TRADE_LOG_PATH', str(tmp_path / 'trade_log.jsonl'))
    monkeypatch.setattr(a, 'POSITIONS_PATH', str(tmp_path / 'positions.json'))
    return tmp_path


@pytest.fixture
def paper_on(monkeypatch):
    monkeypatch.setattr(a, '_ENV_LOADED', True)
    monkeypatch.setenv('ALPACA_PAPER_MODE', 'true')


@pytest.fixture
def paper_off(monkeypatch):
    monkeypatch.setattr(a, '_ENV_LOADED', True)
    monkeypatch.delenv('ALPACA_PAPER_MODE', raising=False)


def fake_order(order_id: str = 'oid-1', fill: str | None = '150.05') -> MagicMock:
    order = MagicMock()
    order.id = order_id
    order.filled_avg_price = fill
    return order


def write_weights(path: str, rows: list[dict]) -> str:
    with open(path, 'w') as f:
        json.dump({'market': 'us', 'generated': '2026-08-28', 'weights': rows}, f)
    return path


class TestPaperModeGuard:
    def test_true_passes(self, paper_on):
        assert a._verify_paper_mode() is None

    def test_false_raises(self, monkeypatch):
        monkeypatch.setenv('ALPACA_PAPER_MODE', 'false')
        with pytest.raises(RuntimeError, match='ALPACA_PAPER_MODE'):
            a._verify_paper_mode()

    def test_missing_raises(self, paper_off):
        with pytest.raises(RuntimeError, match='ALPACA_PAPER_MODE'):
            a._verify_paper_mode()

    def test_execute_blocked_before_any_sdk_call(self, paper_off):
        with patch.object(a, '_client') as client, patch.object(a, '_get_last_price') as price:
            with pytest.raises(RuntimeError, match='ALPACA_PAPER_MODE'):
                a.place_order('AAPL', 10, 'buy', dry_run=False)
        client.assert_not_called()
        price.assert_not_called()


class TestTickerMapping:
    def test_brk_roundtrip(self):
        assert a.to_alpaca_ticker('BRK-B') == 'BRK.B'
        assert a.from_alpaca_ticker('BRK.B') == 'BRK-B'

    def test_identity_for_plain_tickers(self):
        for t in ['VOO', 'AAPL', 'GOOGL', 'NVDA', 'JNJ', 'KO', 'COST', 'MSFT']:
            assert a.from_alpaca_ticker(a.to_alpaca_ticker(t)) == t

    def test_maps_are_inverses(self):
        assert {v: k for k, v in a.TICKER_MAP.items()} == a.TICKER_MAP_BACK


class TestAccountReads:
    def test_get_account(self):
        acct = MagicMock(equity='100000.00', buying_power='50000', cash='25000.5', portfolio_value='100000')
        with patch.object(a, '_client') as client:
            client.return_value.get_account.return_value = acct
            out = a.get_account()
        assert out == {'equity': 100000.0, 'buying_power': 50000.0, 'cash': 25000.5, 'portfolio_value': 100000.0}

    def test_get_positions_maps_tickers(self):
        pos = MagicMock(symbol='BRK.B', qty='10', market_value='4500', current_price='450',
                        avg_entry_price='440', unrealized_pl='100')
        with patch.object(a, '_client') as client:
            client.return_value.get_all_positions.return_value = [pos]
            out = a.get_positions()
        assert out == [{
            'ticker': 'BRK-B', 'qty': 10.0, 'market_value': 4500.0,
            'current_price': 450.0, 'avg_entry_price': 440.0, 'unrealized_pl': 100.0,
        }]

    def test_get_positions_empty(self):
        with patch.object(a, '_client') as client:
            client.return_value.get_all_positions.return_value = []
            assert a.get_positions() == []

    def test_client_paper_flag_from_base_url(self, monkeypatch):
        monkeypatch.setenv('ALPACA_BASE_URL', 'https://paper-api.alpaca.markets')
        with patch('alpaca.trading.client.TradingClient') as tc:
            a._client()
        assert tc.call_args.kwargs['paper'] is True


class TestLimitPrice:
    def test_buy_above_last(self):
        assert a.limit_price(150.0, 'buy') == round(150.0 * 1.001, 2)

    def test_sell_below_last(self):
        assert a.limit_price(150.0, 'sell') == round(150.0 * 0.999, 2)

    def test_last_price_mid_and_fallback(self):
        quote = MagicMock(ask_price='101', bid_price='99')
        with patch('alpaca.data.historical.StockHistoricalDataClient') as dc:
            dc.return_value.get_stock_latest_quote.return_value = {'AAPL': quote}
            assert a._get_last_price('AAPL') == 100.0
            quote.bid_price = None
            assert a._get_last_price('AAPL') == 50.5


class TestPlaceOrder:
    def test_dry_run_is_default_and_touches_nothing(self, isolated_paths):
        with patch.object(a, '_client') as client:
            out = a.place_order('AAPL', 10, 'buy')
        client.assert_not_called()
        assert out['status'] == 'dry_run' and out['dry_run'] is True
        assert out['order_id'] is None and out['limit_price'] is None
        assert out['timestamp'].endswith('+00:00')
        assert not os.path.exists(a.TRADE_LOG_PATH)

    def test_dry_run_maps_ticker(self):
        out = a.place_order('BRK-B', 5, 'sell', dry_run=True)
        assert (out['ticker'], out['alpaca_ticker'], out['side']) == ('BRK-B', 'BRK.B', 'sell')

    def test_execute_submits_limit_order_and_logs(self, paper_on, isolated_paths):
        from alpaca.trading.enums import OrderSide, TimeInForce
        from alpaca.trading.requests import LimitOrderRequest
        with patch.object(a, '_get_last_price', return_value=150.0), patch.object(a, '_client') as client:
            client.return_value.submit_order.return_value = fake_order('oid-9', '150.10')
            out = a.place_order('AAPL', 10, 'buy', dry_run=False)
        req = client.return_value.submit_order.call_args[0][0]
        assert isinstance(req, LimitOrderRequest)
        assert req.symbol == 'AAPL' and req.qty == 10
        assert req.side == OrderSide.BUY and req.time_in_force == TimeInForce.DAY
        assert req.limit_price == 150.15
        assert out['status'] == 'submitted' and out['order_id'] == 'oid-9'
        assert out['filled_avg_price'] == 150.10
        assert out['slippage_pct'] == pytest.approx((150.10 - 150.15) / 150.15 * 100, abs=1e-4)
        with open(a.TRADE_LOG_PATH) as f:
            rows = [json.loads(line) for line in f]
        assert len(rows) == 1 and rows[0]['order_id'] == 'oid-9'
        assert rows[0]['timestamp'].endswith('+00:00')

    def test_execute_sell_side(self, paper_on):
        from alpaca.trading.enums import OrderSide
        with patch.object(a, '_get_last_price', return_value=200.0), patch.object(a, '_client') as client:
            client.return_value.submit_order.return_value = fake_order(fill=None)
            out = a.place_order('KO', 3, 'sell', dry_run=False)
        req = client.return_value.submit_order.call_args[0][0]
        assert req.side == OrderSide.SELL and req.limit_price == 199.8
        assert out['filled_avg_price'] is None and out['slippage_pct'] is None

    def test_log_trade_appends_jsonl(self, isolated_paths):
        a.log_trade({'a': 1})
        a.log_trade({'b': 2})
        with open(a.TRADE_LOG_PATH) as f:
            rows = [json.loads(line) for line in f]
        assert rows == [{'a': 1}, {'b': 2}]


class TestPlanTrades:
    def test_sells_before_buys_and_zero_price_skipped(self):
        trades = a.plan_trades(
            {'AAPL': 0.3, 'GOOGL': 0.7, 'ZERO': 0.1, 'NOPRICE': 0.1},
            100000, {'AAPL': 150.0, 'GOOGL': 100.0, 'ZERO': 0.0}, {'AAPL': 500},
        )
        assert [t['ticker'] for t in trades] == ['AAPL', 'GOOGL']
        assert trades[0] == {
            'ticker': 'AAPL', 'current_shares': 500, 'target_shares': 200, 'diff': -300,
            'side': 'sell', 'qty': 300, 'price': 150.0, 'estimated_value': 45000.0,
        }
        assert trades[1]['side'] == 'buy' and trades[1]['qty'] == 700

    def test_sell_order_is_stable(self):
        trades = a.plan_trades(
            {'A': 0.1, 'B': 0.1, 'C': 0.1, 'D': 0.1}, 1000,
            {'A': 1.0, 'B': 1.0, 'C': 1.0, 'D': 1.0}, {'A': 500, 'B': 0, 'C': 500, 'D': 0},
        )
        assert [t['ticker'] for t in trades] == ['A', 'C', 'B', 'D']

    def test_balanced_portfolio_has_no_trades(self):
        assert a.plan_trades({'AAPL': 0.5}, 100000, {'AAPL': 150.0}, {'AAPL': 333}) == []

    def test_empty_targets(self):
        assert a.plan_trades({}, 100000, {}, {}) == []

    def test_truncates_toward_zero(self):
        trades = a.plan_trades({'X': 0.5}, 1000, {'X': 3.0}, {})
        assert trades[0]['target_shares'] == 166

    def test_output_is_json_serializable(self):
        trades = a.plan_trades({'AAPL': 0.5}, 100000, {'AAPL': 150.0}, {})
        json.dumps(trades)
        assert type(trades[0]['qty']) is int and type(trades[0]['price']) is float


class TestRebalance:
    def test_dry_run_orders_and_positions_file(self, isolated_paths):
        with patch.object(a, 'get_positions', return_value=[{'ticker': 'AAPL', 'qty': 500.0}]), \
             patch.object(a, 'place_order', wraps=a.place_order) as po, \
             patch.object(a, '_client') as client:
            trades = a.rebalance({'AAPL': 0.3, 'GOOGL': 0.7}, 100000, {'AAPL': 150.0, 'GOOGL': 100.0})
        client.assert_not_called()
        assert [c.args[:3] for c in po.call_args_list] == [('AAPL', 300, 'sell'), ('GOOGL', 700, 'buy')]
        assert all(c.kwargs == {'dry_run': True} for c in po.call_args_list)
        assert all(t['status'] == 'dry_run' and t['order_id'] is None for t in trades)
        with open(a.POSITIONS_PATH) as f:
            saved = json.load(f)
        assert saved['capital'] == 100000
        by = {p['ticker']: p for p in saved['positions']}
        assert by['AAPL'] == {
            'ticker': 'AAPL', 'current_shares': 500, 'target_shares': 200, 'current_weight': 75.0,
            'target_weight': 30.0, 'drift_pct': 45.0, 'market_value': 75000.0, 'price': 150.0,
        }
        assert by['GOOGL']['current_shares'] == 0 and by['GOOGL']['drift_pct'] == 70.0
        assert [p for p in os.listdir(isolated_paths) if p.endswith('.tmp')] == []

    def test_positions_unavailable_plans_from_zero(self, capsys):
        with patch.object(a, 'get_positions', side_effect=RuntimeError('no creds')):
            trades = a.rebalance({'AAPL': 0.5}, 100000, {'AAPL': 100.0})
        assert trades[0]['current_shares'] == 0 and trades[0]['qty'] == 500
        assert 'positions unavailable' in capsys.readouterr().err

    def test_execute_passes_dry_run_false(self, paper_on):
        with patch.object(a, 'get_positions', return_value=[]), \
             patch.object(a, 'place_order', return_value={'status': 'submitted', 'order_id': 'x'}) as po:
            trades = a.rebalance({'AAPL': 0.5}, 100000, {'AAPL': 100.0}, dry_run=False)
        assert po.call_args.kwargs == {'dry_run': False}
        assert trades[0]['status'] == 'submitted' and trades[0]['order_id'] == 'x'

    def test_save_positions_zero_price(self, isolated_paths):
        a.save_positions({'X': 0.5}, {'X': 0.0}, {}, 1000)
        with open(a.POSITIONS_PATH) as f:
            pos = json.load(f)['positions']
        assert pos[0]['target_shares'] == 0 and pos[0]['market_value'] == 0.0


class TestCli:
    def test_load_targets_reads_contract(self, tmp_path):
        path = write_weights(str(tmp_path / 'us.json'), [
            {'ticker': 'AAPL', 'weight_pct': 40.0, 'price': 150.0},
            {'ticker': 'BRK-B', 'weight_pct': 60, 'price': '450.5'},
        ])
        target, prices, data = a.load_targets(path)
        assert target == {'AAPL': 0.4, 'BRK-B': 0.6}
        assert prices == {'AAPL': 150.0, 'BRK-B': 450.5}
        assert data['generated'] == '2026-08-28'

    def test_load_targets_missing_weights(self, tmp_path):
        path = str(tmp_path / 'us.json')
        with open(path, 'w') as f:
            json.dump({'market': 'us'}, f)
        with pytest.raises(RuntimeError, match='weights'):
            a.load_targets(path)
        with pytest.raises(RuntimeError):
            a.load_targets(str(tmp_path / 'absent.json'))

    def test_dry_run_prints_plan_and_submits_nothing(self, tmp_path, capsys, paper_on):
        path = write_weights(str(tmp_path / 'us.json'), [
            {'ticker': 'AAPL', 'weight_pct': 40.0, 'price': 150.0},
            {'ticker': 'GOOGL', 'weight_pct': 60.0, 'price': 100.0},
        ])
        with patch.object(a, 'get_positions', return_value=[]), patch.object(a, '_client') as client:
            assert a.main(['--weights', path]) == 0
        client.assert_not_called()
        client.return_value.submit_order.assert_not_called()
        out = json.loads(capsys.readouterr().out)
        assert out['dry_run'] is True and out['capital'] == 100000.0
        assert out['weights_generated'] == '2026-08-28'
        assert [(t['ticker'], t['side'], t['qty']) for t in out['trades']] == [('AAPL', 'buy', 266), ('GOOGL', 'buy', 600)]
        assert out['total_trade_value'] == pytest.approx(266 * 150.0 + 600 * 100.0)
        assert all(t['status'] == 'dry_run' for t in out['trades'])
        assert not os.path.exists(a.TRADE_LOG_PATH)

    def test_capital_flag(self, tmp_path, capsys):
        path = write_weights(str(tmp_path / 'us.json'), [{'ticker': 'AAPL', 'weight_pct': 100.0, 'price': 100.0}])
        with patch.object(a, 'get_positions', return_value=[]):
            assert a.main(['--weights', path, '--capital', '5000']) == 0
        out = json.loads(capsys.readouterr().out)
        assert out['capital'] == 5000.0 and out['trades'][0]['qty'] == 50

    def test_execute_without_paper_mode_returns_1(self, tmp_path, capsys, paper_off):
        path = write_weights(str(tmp_path / 'us.json'), [{'ticker': 'AAPL', 'weight_pct': 100.0, 'price': 100.0}])
        with patch.object(a, 'get_positions', return_value=[]), patch.object(a, '_client') as client:
            assert a.main(['--weights', path, '--execute']) == 1
        client.return_value.submit_order.assert_not_called()
        captured = capsys.readouterr()
        assert captured.out == '' and 'ALPACA_PAPER_MODE' in captured.err

    def test_missing_weights_file_returns_2(self, tmp_path, capsys):
        assert a.main(['--weights', str(tmp_path / 'absent.json')]) == 2
        assert capsys.readouterr().out == ''

    def test_module_imports_without_alpaca_sdk(self):
        code = (
            'import sys; sys.modules["alpaca"] = None\n'
            'import quantshield.broker.alpaca as a\n'
            'print(a.place_order("AAPL", 1, "buy")["status"])\n'
        )
        env = {**os.environ, 'PYTHONPATH': os.getcwd()}
        proc = subprocess.run([sys.executable, '-c', code], capture_output=True, text=True, env=env)
        assert proc.returncode == 0, proc.stderr
        assert proc.stdout.strip() == 'dry_run'
