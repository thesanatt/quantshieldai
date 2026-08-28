from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd
from dotenv import load_dotenv as _load_dotenv

from quantshield.paths import DASHBOARD, PORTFOLIO
from quantshield.utils import append_jsonl, atomic_write_json, load_json, log

if TYPE_CHECKING:
    from alpaca.trading.client import TradingClient


TICKER_MAP = {'BRK-B': 'BRK.B'}
TICKER_MAP_BACK = {v: k for k, v in TICKER_MAP.items()}
TRADE_LOG_PATH = str(PORTFOLIO / 'trade_log.jsonl')
POSITIONS_PATH = str(PORTFOLIO / 'positions.json')
DEFAULT_WEIGHTS_PATH = str(DASHBOARD / 'src' / 'data' / 'us.json')
DEFAULT_CAPITAL = 100000.0
LIMIT_BAND = 0.001


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


_ENV_LOADED = False


def load_dotenv() -> bool:
    global _ENV_LOADED
    if _ENV_LOADED:
        return False
    _ENV_LOADED = True
    return bool(_load_dotenv())


def _client() -> TradingClient:
    from alpaca.trading.client import TradingClient

    load_dotenv()
    api_key = os.environ.get('ALPACA_API_KEY', '')
    secret_key = os.environ.get('ALPACA_SECRET_KEY', '')
    base_url = os.environ.get('ALPACA_BASE_URL', 'https://paper-api.alpaca.markets')
    return TradingClient(api_key, secret_key, paper='paper' in base_url)


def to_alpaca_ticker(ticker: str) -> str:
    return TICKER_MAP.get(ticker, ticker)


def from_alpaca_ticker(ticker: str) -> str:
    return TICKER_MAP_BACK.get(ticker, ticker)


def get_account() -> dict[str, float]:
    acct = _client().get_account()
    return {
        'equity': float(acct.equity),
        'buying_power': float(acct.buying_power),
        'cash': float(acct.cash),
        'portfolio_value': float(acct.portfolio_value),
    }


def get_positions() -> list[dict]:
    return [
        {
            'ticker': from_alpaca_ticker(p.symbol),
            'qty': float(p.qty),
            'market_value': float(p.market_value),
            'current_price': float(p.current_price),
            'avg_entry_price': float(p.avg_entry_price),
            'unrealized_pl': float(p.unrealized_pl),
        }
        for p in _client().get_all_positions()
    ]


def _verify_paper_mode() -> None:
    load_dotenv()
    if os.environ.get('ALPACA_PAPER_MODE', '').lower() != 'true':
        raise RuntimeError(
            'ALPACA_PAPER_MODE is not set to true; refusing to submit orders. '
            'Set ALPACA_PAPER_MODE=true in .env to enable paper execution.'
        )


def _get_last_price(alpaca_ticker: str) -> float:
    from alpaca.data.historical import StockHistoricalDataClient
    from alpaca.data.requests import StockLatestQuoteRequest

    api_key = os.environ.get('ALPACA_API_KEY', '')
    secret_key = os.environ.get('ALPACA_SECRET_KEY', '')
    data_client = StockHistoricalDataClient(api_key, secret_key)
    quote = data_client.get_stock_latest_quote(StockLatestQuoteRequest(symbol_or_symbols=alpaca_ticker))[alpaca_ticker]
    ask, bid = float(quote.ask_price or 0.0), float(quote.bid_price or 0.0)
    mid = (ask + bid) / 2.0
    return mid if mid > 0 else ask


def limit_price(last_price: float, side: str) -> float:
    band = 1.0 + LIMIT_BAND if side == 'buy' else 1.0 - LIMIT_BAND
    return round(last_price * band, 2)


def place_order(ticker: str, qty: int, side: str, dry_run: bool = True) -> dict:
    alpaca_ticker = to_alpaca_ticker(ticker)
    order_info: dict = {
        'ticker': ticker,
        'alpaca_ticker': alpaca_ticker,
        'qty': int(qty),
        'side': side,
        'dry_run': dry_run,
        'timestamp': _utc_now(),
        'status': 'dry_run',
        'order_id': None,
        'limit_price': None,
        'filled_avg_price': None,
        'slippage_pct': None,
    }
    if dry_run:
        return order_info

    _verify_paper_mode()
    from alpaca.trading.enums import OrderSide, TimeInForce
    from alpaca.trading.requests import LimitOrderRequest

    price = limit_price(_get_last_price(alpaca_ticker), side)
    request = LimitOrderRequest(
        symbol=alpaca_ticker,
        qty=int(qty),
        side=OrderSide.BUY if side == 'buy' else OrderSide.SELL,
        time_in_force=TimeInForce.DAY,
        limit_price=price,
    )
    order = _client().submit_order(request)
    fill = float(order.filled_avg_price) if order.filled_avg_price else None
    order_info.update({
        'status': 'submitted',
        'order_id': str(order.id),
        'limit_price': price,
        'filled_avg_price': fill,
        'slippage_pct': round((fill - price) / price * 100, 4) if fill and price > 0 else None,
    })
    log_trade(order_info)
    return order_info


def plan_trades(
    target_weights: dict[str, float],
    total_capital: float,
    current_prices: dict[str, float],
    current_shares: dict[str, float],
) -> list[dict]:
    if not target_weights:
        return []
    df = pd.DataFrame({'weight': pd.Series(target_weights, dtype=float)})
    df['price'] = pd.Series(current_prices, dtype=float).reindex(df.index).fillna(0.0)
    df['current_shares'] = pd.Series(current_shares, dtype=float).reindex(df.index).fillna(0.0).astype(int)
    df = df[df['price'] > 0].copy()
    df['target_shares'] = (df['weight'] * total_capital / df['price']).astype(int)
    df['diff'] = df['target_shares'] - df['current_shares']
    df = df[df['diff'] != 0].copy()
    df['side'] = np.where(df['diff'] > 0, 'buy', 'sell')
    df['qty'] = df['diff'].abs()
    df['estimated_value'] = (df['qty'] * df['price']).round(2)
    df = df.iloc[np.argsort(df['side'].eq('buy').to_numpy(), kind='stable')]
    df.index.name = 'ticker'
    cols = ['ticker', 'current_shares', 'target_shares', 'diff', 'side', 'qty', 'price', 'estimated_value']
    return df.reset_index()[cols].to_dict('records')


def rebalance(
    target_weights: dict[str, float],
    total_capital: float,
    current_prices: dict[str, float],
    dry_run: bool = True,
) -> list[dict]:
    try:
        positions = get_positions()
    except Exception as exc:
        log(f'positions unavailable, planning from zero holdings: {exc}', 'alpaca')
        positions = []
    held = {p['ticker']: p['qty'] for p in positions}
    trades = plan_trades(target_weights, total_capital, current_prices, held)
    for trade in trades:
        result = place_order(trade['ticker'], trade['qty'], trade['side'], dry_run=dry_run)
        trade['status'] = result['status']
        trade['order_id'] = result['order_id']
    save_positions(target_weights, current_prices, held, total_capital)
    return trades


def log_trade(trade_info: dict) -> None:
    append_jsonl(TRADE_LOG_PATH, trade_info)


def save_positions(
    target_weights: dict[str, float],
    current_prices: dict[str, float],
    current_shares: dict[str, float],
    total_capital: float,
) -> None:
    df = pd.DataFrame({'target_weight': pd.Series(target_weights, dtype=float)})
    df['price'] = pd.Series(current_prices, dtype=float).reindex(df.index).fillna(0.0)
    df['current_shares'] = pd.Series(current_shares, dtype=float).reindex(df.index).fillna(0.0).astype(int)
    safe_price = df['price'].where(df['price'] > 0, np.nan)
    df['target_shares'] = (df['target_weight'] * total_capital / safe_price).fillna(0.0).astype(int)
    df['market_value'] = (df['current_shares'] * df['price']).round(2)
    df['current_weight'] = (df['market_value'] / total_capital * 100).round(2) if total_capital > 0 else 0.0
    df['target_weight'] = (df['target_weight'] * 100).round(2)
    df['drift_pct'] = (df['target_weight'] - df['current_weight']).abs().round(2)
    df['price'] = df['price'].round(2)
    df.index.name = 'ticker'
    cols = ['ticker', 'current_shares', 'target_shares', 'current_weight', 'target_weight', 'drift_pct', 'market_value', 'price']
    atomic_write_json(POSITIONS_PATH, {
        'capital': total_capital,
        'last_update': _utc_now(),
        'positions': df.reset_index()[cols].to_dict('records'),
    })


def load_targets(weights_path: str) -> tuple[dict[str, float], dict[str, float], dict]:
    data = load_json(weights_path)
    if not isinstance(data, dict) or not isinstance(data.get('weights'), list):
        raise RuntimeError(f'{weights_path} has no weights list; run the research engine first')
    rows = data['weights']
    target = {r['ticker']: float(r['weight_pct']) / 100.0 for r in rows}
    prices = {r['ticker']: float(r['price']) for r in rows}
    return target, prices, data


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog='python -m quantshield.broker.alpaca')
    parser.add_argument('--weights', default=DEFAULT_WEIGHTS_PATH)
    parser.add_argument('--capital', type=float, default=DEFAULT_CAPITAL)
    parser.add_argument('--execute', action='store_true')
    args = parser.parse_args(argv)

    try:
        target, prices, data = load_targets(args.weights)
    except RuntimeError as exc:
        log(str(exc), 'alpaca')
        return 2
    dry_run = not args.execute
    try:
        trades = rebalance(target, args.capital, prices, dry_run=dry_run)
    except RuntimeError as exc:
        log(str(exc), 'alpaca')
        return 1
    print(json.dumps({
        'generated': _utc_now(),
        'dry_run': dry_run,
        'weights_generated': data.get('generated'),
        'capital': args.capital,
        'trades': trades,
        'total_trade_value': round(sum(t['estimated_value'] for t in trades), 2),
    }, indent=2))
    return 0


if __name__ == '__main__':
    sys.exit(main())
