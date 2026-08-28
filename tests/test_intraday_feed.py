import json
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest

import quantshield.intraday.candles as candles
import quantshield.intraday.feed as feed
from quantshield.intraday.feed import BarAggregator, append_bar, session_bounds


def ts(h: int, m: int, s: int) -> datetime:
    return datetime(2026, 7, 21, h, m, s)


def test_single_bar_ohlc() -> None:
    agg = BarAggregator()
    assert agg.on_tick(1, 100.0, 1000, ts(9, 15, 1)) == []
    assert agg.on_tick(1, 102.0, 1500, ts(9, 15, 20)) == []
    assert agg.on_tick(1, 99.0, 2000, ts(9, 15, 40)) == []
    done = agg.on_tick(1, 101.0, 2500, ts(9, 16, 2))
    assert len(done) == 1
    bar = done[0]
    assert bar['open'] == 100.0
    assert bar['high'] == 102.0
    assert bar['low'] == 99.0
    assert bar['close'] == 99.0
    assert bar['ticks'] == 3


def test_first_bar_volume_uses_first_seen_cumulative() -> None:
    agg = BarAggregator()
    agg.on_tick(1, 100.0, 50000, ts(10, 0, 5))
    agg.on_tick(1, 100.5, 53000, ts(10, 0, 50))
    done = agg.on_tick(1, 101.0, 54000, ts(10, 1, 1))
    assert done[0]['volume'] == 3000


def test_subsequent_bar_volume_is_cumulative_diff() -> None:
    agg = BarAggregator()
    agg.on_tick(1, 100.0, 1000, ts(9, 15, 1))
    agg.on_tick(1, 100.0, 4000, ts(9, 15, 59))
    agg.on_tick(1, 100.0, 9000, ts(9, 16, 30))
    done = agg.on_tick(1, 100.0, 9500, ts(9, 17, 0))
    assert done[0]['volume'] == 5000


def test_tokens_isolated() -> None:
    agg = BarAggregator()
    agg.on_tick(1, 100.0, 100, ts(9, 15, 5))
    agg.on_tick(2, 500.0, 900, ts(9, 15, 6))
    done = agg.on_tick(1, 101.0, 200, ts(9, 16, 0))
    assert len(done) == 1
    assert done[0]['open'] == 100.0
    assert 2 in agg.current


def test_index_ticks_without_volume() -> None:
    agg = BarAggregator()
    agg.on_tick(9, 25000.0, None, ts(9, 15, 10))
    done = agg.on_tick(9, 25010.0, None, ts(9, 16, 10))
    assert done[0]['volume'] == 0


def test_flush_emits_open_bars() -> None:
    agg = BarAggregator()
    agg.on_tick(1, 100.0, 1000, ts(15, 29, 55))
    agg.on_tick(2, 200.0, 2000, ts(15, 29, 56))
    flushed = agg.flush()
    assert set(flushed) == {1, 2}
    assert agg.current == {}


def test_append_bar_writes_jsonl(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(feed, 'TICKS_DIR', str(tmp_path))
    bar = {'ts': '2026-07-21T09:16:00', 'open': 1, 'high': 2, 'low': 0.5, 'close': 1.5, 'volume': 10, 'ticks': 4}
    append_bar('NIFTYBEES', bar, '2026-07-21')
    append_bar('NIFTYBEES', bar, '2026-07-21')
    lines = (tmp_path / '2026-07-21' / 'NIFTYBEES.jsonl').read_text().strip().split('\n')
    assert len(lines) == 2
    assert json.loads(lines[0])['close'] == 1.5


def test_session_bounds_weekend() -> None:
    assert session_bounds(datetime(2026, 7, 19, 10, 0)) is None
    assert session_bounds(datetime(2026, 7, 18, 10, 0)) is None


def test_session_bounds_india_holiday() -> None:
    assert session_bounds(datetime(2026, 10, 2, 10, 0)) is None
    assert session_bounds(datetime(2026, 1, 26, 10, 0)) is None


def test_session_bounds_weekday() -> None:
    bounds = session_bounds(datetime(2026, 7, 21, 10, 0))
    assert bounds is not None
    open_dt, close_dt = bounds
    assert (open_dt.hour, open_dt.minute) == (9, 15)
    assert (close_dt.hour, close_dt.minute) == (15, 30)


def test_heartbeat_contract(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(feed, 'HEARTBEAT_PATH', str(tmp_path / 'feed_heartbeat.json'))
    feed.write_heartbeat({'connected': True, 'bars': 7, 'last_tick': '2026-07-21T09:16:00', 'auth_fail': 0})
    hb = json.loads((tmp_path / 'feed_heartbeat.json').read_text())
    stamp = datetime.fromisoformat(hb['ts'])
    assert stamp.utcoffset() is not None and stamp.utcoffset().total_seconds() == 0
    assert hb['bars_written'] == 7
    assert hb['connected'] is True


def test_exit_codes_are_stable() -> None:
    assert feed.AUTH_NEEDED_EXIT == 3
    assert feed.STALE_AUTH_EXIT == 4
    assert feed.HEARTBEAT_PATH.endswith('data/intraday/feed_heartbeat.json')


class FakeKite:
    def __init__(self, rows: list[dict]) -> None:
        self.rows = rows
        self.calls = 0

    def instruments(self, exchange: str) -> list[dict]:
        self.calls += 1
        return self.rows


def test_resolve_tokens_uses_one_instrument_lookup(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(candles, '_INSTRUMENTS', {})
    kite = FakeKite([{'tradingsymbol': s, 'instrument_token': i} for i, s in enumerate(feed.SYMBOLS, start=11)])
    tokens = feed.resolve_tokens(kite)
    assert tokens[candles.NIFTY_INDEX_TOKEN] == 'NIFTY50'
    assert set(tokens.values()) == {'NIFTY50', *feed.SYMBOLS}
    assert kite.calls == 1


def test_resolve_tokens_missing_symbol_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(candles, '_INSTRUMENTS', {})
    kite: Any = FakeKite([{'tradingsymbol': 'NIFTYBEES', 'instrument_token': 1}])
    with pytest.raises(RuntimeError):
        feed.resolve_tokens(kite)
