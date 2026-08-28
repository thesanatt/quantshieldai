import argparse
import json
import os
import time
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any

from quantshield.paths import INTRADAY
from quantshield.utils import log, now_ist, read_jsonl

CANDLES_DIR = str(INTRADAY / 'candles')
SYMBOLS = ('NIFTYBEES', 'SBIN', 'BAJFINANCE')
NIFTY_INDEX_TOKEN = 256265
SESSION_OPEN = (9, 15)
SESSION_CLOSE = (15, 30)
CHUNK_DAYS = 55
FETCH_PAUSE_S = 0.4
_INSTRUMENTS: dict[str, dict[str, int]] = {}


def to_bar(candle: dict) -> dict:
    return {
        'ts': candle['date'].replace(tzinfo=None).isoformat(),
        'open': candle['open'], 'high': candle['high'], 'low': candle['low'],
        'close': candle['close'], 'volume': candle.get('volume', 0),
    }


def instrument_token(kite: Any, symbol: str, exchange: str = 'NSE') -> int | None:
    if exchange not in _INSTRUMENTS:
        _INSTRUMENTS[exchange] = {
            inst['tradingsymbol']: int(inst['instrument_token']) for inst in kite.instruments(exchange)
        }
    return _INSTRUMENTS[exchange].get(symbol)


def fetch_minute_bars(kite: Any, token: int, start: datetime, end: datetime) -> dict[str, list[dict]]:
    by_day: dict[str, list[dict]] = defaultdict(list)
    cursor = start
    while cursor < end:
        chunk_end = min(cursor + timedelta(days=CHUNK_DAYS), end)
        candles = kite.historical_data(token, cursor, chunk_end, 'minute')
        for bar in map(to_bar, candles):
            by_day[bar['ts'][:10]].append(bar)
        log(f'{token} {cursor.date()} -> {chunk_end.date()}: {len(candles)} candles', 'candles')
        cursor = chunk_end
        if cursor < end:
            time.sleep(FETCH_PAUSE_S)
    return dict(by_day)


def day_path(symbol: str, day: str, base_dir: str = CANDLES_DIR) -> str:
    return os.path.join(base_dir, day, f'{symbol}.jsonl')


def write_day(symbol: str, day: str, bars: list[dict], candles_dir: str = CANDLES_DIR) -> str:
    path = day_path(symbol, day, candles_dir)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w') as f:
        f.writelines(json.dumps(b) + '\n' for b in bars)
    return path


def read_day(symbol: str, day: str, candles_dir: str = CANDLES_DIR) -> list[dict]:
    return read_jsonl(day_path(symbol, day, candles_dir))


def session_window(day: datetime) -> tuple[datetime, datetime]:
    start = day.replace(hour=SESSION_OPEN[0], minute=SESSION_OPEN[1], second=0, microsecond=0)
    end = day.replace(hour=SESSION_CLOSE[0], minute=SESSION_CLOSE[1], second=0, microsecond=0)
    return start, min(end, now_ist())


def backfill(day: str, symbols: tuple[str, ...] = SYMBOLS, candles_dir: str = CANDLES_DIR) -> dict:
    from quantshield.broker.zerodha import _client
    kite = _client()
    start, end = session_window(datetime.strptime(day, '%Y-%m-%d'))
    if end <= start:
        log(f'{day}: session has not started; nothing to fetch', 'candles')
        return {'ok': False, 'date': day, 'candles': 0}
    tokens: dict[str, int] = {'NIFTY50': NIFTY_INDEX_TOKEN}
    for sym in symbols:
        tok = instrument_token(kite, sym)
        if tok is None:
            log(f'no instrument token for {sym}; skipping', 'candles')
            continue
        tokens[sym] = tok
    total = 0
    for sym, tok in tokens.items():
        try:
            bars = fetch_minute_bars(kite, tok, start, end).get(day, [])
        except Exception as exc:
            log(f'{sym} fetch failed: {exc}', 'candles')
            continue
        write_day(sym, day, bars, candles_dir)
        total += len(bars)
        log(f'{sym}: {len(bars)} candles', 'candles')
    return {'ok': True, 'date': day, 'candles': total}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--date', default=None)
    parser.add_argument('--candles-dir', default=CANDLES_DIR)
    args = parser.parse_args()
    day = args.date or now_ist().strftime('%Y-%m-%d')
    print(json.dumps(backfill(day, candles_dir=args.candles_dir)))


if __name__ == '__main__':
    main()
