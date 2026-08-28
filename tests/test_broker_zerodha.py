import json
import os
import sys
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

import quantshield.broker.zerodha as z


@pytest.fixture
def token_path(tmp_path, monkeypatch):
    path = str(tmp_path / '.zerodha_access_token.json')
    monkeypatch.setattr(z, 'ACCESS_TOKEN_PATH', path)
    return path


@pytest.fixture
def creds(monkeypatch):
    monkeypatch.setattr(z, '_ENV_LOADED', True)
    monkeypatch.setenv('KITE_API_KEY', 'key123')
    monkeypatch.setenv('KITE_API_SECRET', 'secret456')


@pytest.fixture
def no_creds(monkeypatch):
    monkeypatch.setattr(z, '_ENV_LOADED', True)
    monkeypatch.delenv('KITE_API_KEY', raising=False)
    monkeypatch.delenv('KITE_API_SECRET', raising=False)


def write_token(path: str, date: str, token: str = 'tok') -> None:
    with open(path, 'w') as f:
        json.dump({'access_token': token, 'date': date}, f)


class TestTokenFile:
    def test_missing_file_means_no_token(self, token_path):
        assert z._load_access_token() is None
        assert z.token_fresh() is False

    def test_save_then_load_same_day(self, token_path):
        z._save_access_token('abc')
        assert z._load_access_token() == 'abc'
        assert z.token_fresh() is True
        with open(token_path) as f:
            rec = json.load(f)
        assert rec['date'] == datetime.now(z.IST).strftime('%Y-%m-%d')
        assert set(rec) == {'access_token', 'date', 'timestamp'}

    def test_stale_token_ignored(self, token_path):
        write_token(token_path, '2020-01-01')
        assert z._load_access_token() is None
        assert z.token_fresh() is False

    def test_corrupt_file_ignored(self, token_path):
        with open(token_path, 'w') as f:
            f.write('{not json')
        assert z._load_access_token() is None

    def test_non_dict_file_ignored(self, token_path):
        with open(token_path, 'w') as f:
            json.dump(['x'], f)
        assert z._load_access_token() is None

    def test_empty_token_string_is_missing(self, token_path):
        write_token(token_path, z._today(), token='')
        assert z._load_access_token() is None

    def test_save_is_atomic(self, token_path, tmp_path):
        z._save_access_token('abc')
        assert [p for p in os.listdir(tmp_path) if p.endswith('.tmp')] == []


class TestCredentials:
    def test_missing_credentials_raise(self, no_creds):
        with pytest.raises(RuntimeError, match='KITE_API_KEY'):
            z._get_api_credentials()

    def test_login_url_contains_key(self, creds):
        url = z.generate_login_url()
        assert url.startswith('https://kite.zerodha.com/connect/login')
        assert 'api_key=key123' in url

    def test_login_url_requires_api_key(self, no_creds):
        with pytest.raises(RuntimeError, match='KITE_API_KEY'):
            z.generate_login_url()


class TestClient:
    def test_missing_token_get_kite_none_and_client_raises(self, token_path, creds):
        with pytest.raises(RuntimeError, match='login-url'):
            z._client()
        assert z.get_kite() is None

    def test_client_error_does_not_leak_api_key(self, token_path, creds):
        with pytest.raises(RuntimeError) as info:
            z._client()
        assert 'key123' not in str(info.value)

    def test_client_without_credentials_raises(self, token_path, no_creds):
        write_token(token_path, z._today())
        with pytest.raises(RuntimeError, match='KITE_API_KEY'):
            z._client()
        assert z.get_kite() is None

    def test_client_needs_only_api_key(self, token_path, monkeypatch):
        monkeypatch.setattr(z, '_ENV_LOADED', True)
        monkeypatch.setenv('KITE_API_KEY', 'key123')
        monkeypatch.delenv('KITE_API_SECRET', raising=False)
        write_token(token_path, z._today(), token='fresh')
        with patch.object(z, '_kite_class', return_value=MagicMock()):
            assert z.get_kite() is not None
        with pytest.raises(RuntimeError, match='KITE_API_SECRET'):
            z.complete_login_with_request_token('req')

    def test_client_sets_access_token(self, token_path, creds):
        write_token(token_path, z._today(), token='fresh')
        kite_cls = MagicMock()
        with patch.object(z, '_kite_class', return_value=kite_cls):
            kite = z._client()
        kite_cls.assert_called_once_with(api_key='key123')
        kite_cls.return_value.set_access_token.assert_called_once_with('fresh')
        assert kite is kite_cls.return_value

    def test_get_kite_returns_client_when_fresh(self, token_path, creds):
        write_token(token_path, z._today())
        with patch.object(z, '_kite_class', return_value=MagicMock()):
            assert z.get_kite() is not None

    def test_sdk_missing_raises_runtime_error(self, token_path, creds):
        write_token(token_path, z._today())
        with patch.dict(sys.modules, {'kiteconnect': None}):
            with pytest.raises(RuntimeError, match='kiteconnect'):
                z._client()

    def test_complete_login_saves_token(self, token_path, creds):
        kite_cls = MagicMock()
        kite_cls.return_value.generate_session.return_value = {'access_token': 'newtok'}
        with patch.object(z, '_kite_class', return_value=kite_cls):
            assert z.complete_login_with_request_token('req') == 'newtok'
        kite_cls.return_value.generate_session.assert_called_once_with('req', api_secret='secret456')
        assert z._load_access_token() == 'newtok'


class TestReads:
    def test_resolve_tokens_downloads_dump_once(self):
        kite = MagicMock()
        kite.instruments.return_value = [
            {'tradingsymbol': 'SBIN', 'instrument_token': '779521'},
            {'tradingsymbol': 'NIFTYBEES', 'instrument_token': 2707457},
            {'tradingsymbol': 'OTHER', 'instrument_token': 1},
        ]
        with patch.object(z, '_client', return_value=kite):
            out = z.resolve_tokens(['SBIN', 'NIFTYBEES', 'MISSING'])
        assert out == {'SBIN': 779521, 'NIFTYBEES': 2707457}
        kite.instruments.assert_called_once_with('NSE')

    def test_resolve_tokens_empty_input_skips_download(self):
        with patch.object(z, '_client') as client:
            assert z.resolve_tokens([]) == {}
        client.assert_not_called()

    def test_lookup_instrument_token(self):
        kite = MagicMock()
        kite.instruments.return_value = [{'tradingsymbol': 'SBIN', 'instrument_token': 779521}]
        with patch.object(z, '_client', return_value=kite):
            assert z.lookup_instrument_token('SBIN') == 779521
            assert z.lookup_instrument_token('NOPE') is None

    def test_get_account_shape(self):
        kite = MagicMock()
        kite.margins.return_value = {
            'available': {'cash': '1000.5'}, 'utilised': {'debits': 12}, 'net': 988.5,
        }
        with patch.object(z, '_client', return_value=kite):
            acct = z.get_account()
        assert acct == {'available_cash': 1000.5, 'used_margin': 12.0, 'net_value': 988.5}
        kite.margins.assert_called_once_with(segment='equity')

    def test_get_positions_filters_zero_qty(self):
        row = {
            'tradingsymbol': 'SBIN', 'exchange': 'NSE', 'instrument_token': 779521,
            'quantity': 5, 'average_price': 700.0, 'last_price': 710.0, 'pnl': 50.0, 'product': 'CNC',
        }
        kite = MagicMock()
        kite.positions.return_value = {'net': [row, {**row, 'tradingsymbol': 'FLAT', 'quantity': 0}]}
        with patch.object(z, '_client', return_value=kite):
            out = z.get_positions()
        assert [p['tradingsymbol'] for p in out] == ['SBIN']
        assert out[0]['quantity'] == 5 and out[0]['pnl'] == 50.0

    def test_get_holdings_shape(self):
        kite = MagicMock()
        kite.holdings.return_value = [{
            'tradingsymbol': 'NIFTYBEES', 'exchange': 'NSE', 'instrument_token': 2707457,
            'quantity': '10', 'average_price': 270.0, 'last_price': 275.5, 'pnl': 55.0,
        }]
        with patch.object(z, '_client', return_value=kite):
            out = z.get_holdings()
        assert out[0]['quantity'] == 10
        assert out[0]['day_change_percentage'] == 0.0
        assert set(out[0]) == {
            'tradingsymbol', 'exchange', 'instrument_token', 'quantity',
            'average_price', 'last_price', 'pnl', 'day_change_percentage',
        }

    def test_reads_raise_without_token(self, token_path, creds):
        for fn in (z.get_account, z.get_positions, z.get_holdings):
            with pytest.raises(RuntimeError):
                fn()


class TestNoOrderPath:
    def test_module_has_no_order_functions(self):
        for name in ('place_order', 'rebalance', 'get_order_status', 'log_trade', 'save_positions', '_verify_live_mode'):
            assert not hasattr(z, name)


class TestCli:
    def test_status_stale(self, token_path, creds, capsys):
        write_token(token_path, '2020-01-01')
        assert z.main(['status']) == 0
        out = json.loads(capsys.readouterr().out)
        assert out['token_fresh'] is False
        assert out['token_date'] == '2020-01-01'
        assert out['credentials_set'] is True
        assert 'access_token' not in out

    def test_status_fresh(self, token_path, creds, capsys):
        z._save_access_token('abc')
        assert z.main(['status']) == 0
        out = json.loads(capsys.readouterr().out)
        assert out['token_fresh'] is True
        assert out['today'] == z._today()
        assert 'abc' not in capsys.readouterr().out

    def test_login_url(self, creds, capsys):
        assert z.main(['login-url']) == 0
        out = json.loads(capsys.readouterr().out)
        assert out['login_url'] == z.generate_login_url()

    def test_login_url_without_credentials_fails(self, no_creds, capsys):
        assert z.main(['login-url']) == 1
        captured = capsys.readouterr()
        assert captured.out == ''
        assert 'KITE_API_KEY' in captured.err

    def test_complete_saves_token_and_hides_it(self, token_path, creds, capsys):
        kite_cls = MagicMock()
        kite_cls.return_value.generate_session.return_value = {'access_token': 'secret-token'}
        with patch.object(z, '_kite_class', return_value=kite_cls):
            assert z.main(['complete', 'req123']) == 0
        out = capsys.readouterr().out
        assert json.loads(out)['ok'] is True
        assert 'secret-token' not in out
        assert z._load_access_token() == 'secret-token'

    def test_complete_failure_returns_1(self, token_path, creds, capsys):
        kite_cls = MagicMock()
        kite_cls.return_value.generate_session.side_effect = ValueError('bad request token')
        with patch.object(z, '_kite_class', return_value=kite_cls):
            assert z.main(['complete', 'req123']) == 1
        captured = capsys.readouterr()
        assert captured.out == ''
        assert 'bad request token' in captured.err
        assert z._load_access_token() is None

    def test_requires_subcommand(self):
        with pytest.raises(SystemExit):
            z.main([])
