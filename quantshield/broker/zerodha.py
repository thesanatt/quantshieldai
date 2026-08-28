from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Iterable
from datetime import datetime
from typing import TYPE_CHECKING

from dotenv import load_dotenv as _load_dotenv

from quantshield.paths import PORTFOLIO
from quantshield.utils import IST, atomic_write_json, load_json, log

if TYPE_CHECKING:
    from kiteconnect import KiteConnect


ACCESS_TOKEN_PATH = str(PORTFOLIO / '.zerodha_access_token.json')
LOGIN_HELP = (
    'Zerodha access token missing or stale. '
    'Run: python -m quantshield.broker.zerodha login-url, open the URL, '
    'then run: python -m quantshield.broker.zerodha complete <request_token>'
)


def _kite_class() -> type:
    try:
        from kiteconnect import KiteConnect
    except ImportError as exc:
        raise RuntimeError('kiteconnect is not installed; run: pip install kiteconnect') from exc
    return KiteConnect


_ENV_LOADED = False


def load_dotenv() -> bool:
    global _ENV_LOADED
    if _ENV_LOADED:
        return False
    _ENV_LOADED = True
    return bool(_load_dotenv())


def _api_key() -> str:
    load_dotenv()
    api_key = os.environ.get('KITE_API_KEY', '')
    if not api_key:
        raise RuntimeError('KITE_API_KEY must be set in the environment')
    return api_key


def _get_api_credentials() -> tuple[str, str]:
    load_dotenv()
    api_secret = os.environ.get('KITE_API_SECRET', '')
    if not api_secret:
        raise RuntimeError('KITE_API_KEY and KITE_API_SECRET must be set in the environment')
    return _api_key(), api_secret


def _today() -> str:
    return datetime.now(IST).strftime('%Y-%m-%d')


def _token_record() -> dict:
    data = load_json(ACCESS_TOKEN_PATH, {})
    return data if isinstance(data, dict) else {}


def _load_access_token() -> str | None:
    record = _token_record()
    if record.get('date') != _today():
        return None
    return record.get('access_token') or None


def _save_access_token(access_token: str) -> None:
    now = datetime.now(IST)
    atomic_write_json(ACCESS_TOKEN_PATH, {
        'access_token': access_token,
        'date': now.strftime('%Y-%m-%d'),
        'timestamp': now.replace(tzinfo=None).isoformat(),
    })


def generate_login_url() -> str:
    return f'https://kite.zerodha.com/connect/login?v=3&api_key={_api_key()}'


def complete_login_with_request_token(request_token: str) -> str:
    api_key, api_secret = _get_api_credentials()
    kite = _kite_class()(api_key=api_key)
    session = kite.generate_session(request_token, api_secret=api_secret)
    access_token = str(session['access_token'])
    _save_access_token(access_token)
    return access_token


def _client() -> KiteConnect:
    api_key = _api_key()
    access_token = _load_access_token()
    if not access_token:
        raise RuntimeError(LOGIN_HELP)
    kite = _kite_class()(api_key=api_key)
    kite.set_access_token(access_token)
    return kite


def token_fresh() -> bool:
    return _load_access_token() is not None


def get_kite() -> KiteConnect | None:
    try:
        return _client()
    except RuntimeError:
        return None


def resolve_tokens(symbols: Iterable[str], exchange: str = 'NSE') -> dict[str, int]:
    wanted = set(symbols)
    if not wanted:
        return {}
    instruments = _client().instruments(exchange)
    return {
        str(inst['tradingsymbol']): int(inst['instrument_token'])
        for inst in instruments
        if inst['tradingsymbol'] in wanted
    }


def lookup_instrument_token(tradingsymbol: str, exchange: str = 'NSE') -> int | None:
    return resolve_tokens([tradingsymbol], exchange).get(tradingsymbol)


def get_account() -> dict[str, float]:
    margins = _client().margins(segment='equity')
    return {
        'available_cash': float(margins['available']['cash']),
        'used_margin': float(margins['utilised']['debits']),
        'net_value': float(margins['net']),
    }


def get_positions() -> list[dict]:
    positions = _client().positions()
    return [
        {
            'tradingsymbol': p['tradingsymbol'],
            'exchange': p['exchange'],
            'instrument_token': int(p['instrument_token']),
            'quantity': int(p['quantity']),
            'average_price': float(p['average_price']),
            'last_price': float(p['last_price']),
            'pnl': float(p['pnl']),
            'product': p['product'],
        }
        for p in positions.get('net', [])
        if p['quantity'] != 0
    ]


def get_holdings() -> list[dict]:
    return [
        {
            'tradingsymbol': h['tradingsymbol'],
            'exchange': h['exchange'],
            'instrument_token': int(h['instrument_token']),
            'quantity': int(h['quantity']),
            'average_price': float(h['average_price']),
            'last_price': float(h['last_price']),
            'pnl': float(h['pnl']),
            'day_change_percentage': float(h.get('day_change_percentage', 0)),
        }
        for h in _client().holdings()
    ]


def status() -> dict:
    record = _token_record()
    today = _today()
    return {
        'token_fresh': record.get('date') == today and bool(record.get('access_token')),
        'token_date': record.get('date'),
        'today': today,
        'credentials_set': bool(load_dotenv() is not None and os.environ.get('KITE_API_KEY') and os.environ.get('KITE_API_SECRET')),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog='python -m quantshield.broker.zerodha')
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('login-url')
    complete = sub.add_parser('complete')
    complete.add_argument('request_token')
    sub.add_parser('status')
    args = parser.parse_args(argv)

    try:
        if args.command == 'login-url':
            out: dict = {'login_url': generate_login_url()}
        elif args.command == 'complete':
            complete_login_with_request_token(args.request_token)
            out = {'ok': True, 'token_date': _today()}
        else:
            out = status()
    except Exception as exc:
        log(f'{type(exc).__name__}: {exc}', 'zerodha')
        return 1
    print(json.dumps(out, indent=2))
    return 0


if __name__ == '__main__':
    sys.exit(main())
