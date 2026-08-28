import json
from pathlib import Path

import pytest

import quantshield.intraday.paper as orb


def bar(hh: int, mm: int, o: float, h: float, lo: float, c: float, v: int = 1000) -> dict:
    return {'ts': f'2026-07-21T{hh:02d}:{mm:02d}:00', 'open': o, 'high': h, 'low': lo, 'close': c, 'volume': v}


def or_bars(high: float = 102.0, low: float = 100.0) -> list[dict]:
    return [bar(9, 15 + i, 101.0, high if i == 10 else 101.2, low if i == 20 else 100.8, 101.0) for i in range(30)]


def flat_bars(start_h: int, start_m: int, count: int, px: float) -> list[dict]:
    bars = []
    h, m = start_h, start_m
    for _ in range(count):
        bars.append(bar(h, m, px, px + 0.05, px - 0.05, px))
        m += 1
        if m == 60:
            m = 0
            h += 1
    return bars


def breakout_session() -> list[dict]:
    bars = or_bars() + flat_bars(9, 45, 15, 101.5)
    bars.append(bar(10, 0, 101.9, 102.5, 101.8, 102.4))
    return bars + flat_bars(10, 1, 320, 103.0)


def test_levels_round_away_from_the_trade() -> None:
    trigger, stop = orb.levels({'high': 102.0, 'low': 100.0})
    assert trigger == pytest.approx(102.01)
    assert stop == pytest.approx(101.0)
    trigger, stop = orb.levels({'high': 297.99, 'low': 296.72})
    assert trigger == pytest.approx(298.0)
    assert stop == pytest.approx(297.35)


def test_no_trigger_session() -> None:
    r = orb.evaluate_session(or_bars() + flat_bars(9, 45, 330, 101.0), '2026-07-21')
    assert r['triggered'] is False
    assert r['net'] == 0.0
    assert r['time_in_market_frac'] == 0.0
    assert r['trigger'] == pytest.approx(102.01)
    assert r['stop'] == pytest.approx(101.0)


def test_trigger_then_time_exit_profit() -> None:
    r = orb.evaluate_session(breakout_session(), '2026-07-21')
    assert r['triggered'] is True
    assert r['entry_px'] == pytest.approx(102.04)
    assert r['exit_reason'] == 'time_exit'
    assert r['qty'] == int(2000 // 102.04)
    assert r['gross'] == pytest.approx(r['qty'] * (r['exit_px'] - r['entry_px']), abs=0.01)
    assert r['net'] < r['gross']
    assert r['costs'] > 0
    assert 0 < r['time_in_market_frac'] <= 1


def test_trigger_then_stop_loss() -> None:
    bars = or_bars() + flat_bars(9, 45, 15, 101.5)
    bars.append(bar(10, 0, 101.9, 102.5, 101.8, 102.4))
    bars += flat_bars(10, 1, 30, 101.5)
    bars.append(bar(10, 31, 101.2, 101.3, 100.9, 101.0))
    bars += flat_bars(10, 32, 280, 101.2)
    r = orb.evaluate_session(bars, '2026-07-21')
    assert r['exit_reason'] == 'stop'
    assert r['exit_px'] == pytest.approx(100.98)
    assert r['net'] < 0


def test_same_bar_stop() -> None:
    bars = or_bars() + flat_bars(9, 45, 15, 101.5)
    bars.append(bar(10, 0, 101.9, 102.5, 100.5, 100.9))
    bars += flat_bars(10, 1, 300, 101.0)
    r = orb.evaluate_session(bars, '2026-07-21')
    assert r['exit_reason'] == 'stop_same_bar'
    assert r['exit_ts'] == r['entry_ts']


def test_entry_deadline_enforced() -> None:
    bars = or_bars() + flat_bars(9, 45, 194, 101.0)
    bars.append(bar(13, 5, 102.0, 103.0, 102.0, 102.8))
    bars += flat_bars(13, 6, 120, 103.0)
    r = orb.evaluate_session(bars, '2026-07-21')
    assert r['triggered'] is False


def test_incomplete_opening_range_returns_none() -> None:
    assert orb.evaluate_session(or_bars()[:10], '2026-07-21') is None


def test_max_gap_detection() -> None:
    bars = or_bars() + flat_bars(9, 45, 10, 101.0) + flat_bars(10, 30, 200, 101.0)
    r = orb.evaluate_session(bars, '2026-07-21')
    assert r['max_gap_min'] >= 30
    assert orb.max_gap_minutes(or_bars(), '15:10') == 0
    assert orb.max_gap_minutes(or_bars()[:1], '15:10') == 0


def test_bench_open_is_first_bar_close_not_auction_open() -> None:
    bars = or_bars() + flat_bars(9, 45, 330, 101.0)
    bars[0] = bar(9, 15, 103.0, 103.2, 100.9, 101.0)
    r = orb.evaluate_session(bars, '2026-07-21')
    assert r['bench_open'] == pytest.approx(101.0)
    assert r['bench_close'] == pytest.approx(101.0)
    assert r['bench_ret_pct'] == pytest.approx(0.0)


def test_signal_gap_stops_at_entry_bar() -> None:
    bars = breakout_session()
    bars = [b for b in bars if not ('10:30' <= b['ts'][11:16] < '11:00')]
    r = orb.evaluate_session(bars, '2026-07-21')
    assert r['triggered'] is True
    assert r['max_gap_min'] >= 29
    assert r['signal_gap_min'] == 0
    assert orb.is_blind(r) is False


def test_signal_gap_before_entry_marks_blind() -> None:
    bars = breakout_session()
    bars = [b for b in bars if not ('09:50' <= b['ts'][11:16] < '09:56')]
    r = orb.evaluate_session(bars, '2026-07-21')
    assert r['triggered'] is True
    assert r['signal_gap_min'] == 6
    assert orb.is_blind(r) is True


def test_untriggered_signal_gap_stops_at_entry_deadline() -> None:
    bars = or_bars() + flat_bars(9, 45, 330, 101.0)
    late_gap = [b for b in bars if not ('14:00' <= b['ts'][11:16] < '14:30')]
    early_gap = [b for b in bars if not ('12:00' <= b['ts'][11:16] < '12:10')]
    assert orb.is_blind(orb.evaluate_session(late_gap, '2026-07-21')) is False
    assert orb.is_blind(orb.evaluate_session(early_gap, '2026-07-21')) is True


def test_record_roundtrip(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(orb, 'TRACK_PATH', str(tmp_path / 'track.jsonl'))
    assert orb.already_recorded('2026-07-21') is False
    orb.append_record({'date': '2026-07-21', 'arm': orb.ARM, 'net': 1.0})
    assert orb.already_recorded('2026-07-21') is True
    assert orb.already_recorded('2026-07-22') is False


def test_load_bars_prefers_official_candles(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(orb, 'TICKS_DIR', str(tmp_path / 'ticks'))
    monkeypatch.setattr(orb, 'CANDLES_DIR', str(tmp_path / 'candles'))
    day = '2026-07-21'
    for base, close in (('ticks', 1.0), ('candles', 2.0)):
        d = tmp_path / base / day
        d.mkdir(parents=True)
        (d / 'NIFTYBEES.jsonl').write_text(json.dumps({'ts': '2026-07-21T09:15:00', 'open': 1, 'high': 2, 'low': 0.5, 'close': close}) + '\n')
    (tmp_path / 'ticks' / day / 'NIFTYBEES.jsonl').open('a').write(json.dumps({'ts': '2026-07-21T09:16:00', 'open': 1, 'high': 2, 'low': 0.5, 'close': 1.5}) + '\n')
    bars = orb.load_bars(day)
    assert [b['close'] for b in bars] == [2.0, 1.5]


def test_finalize_day_writes_blind_flag(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(orb, 'TRACK_PATH', str(tmp_path / 'track.jsonl'))
    monkeypatch.setattr(orb, 'TICKS_DIR', str(tmp_path / 'ticks'))
    monkeypatch.setattr(orb, 'CANDLES_DIR', str(tmp_path / 'candles'))
    day = '2026-07-21'
    d = tmp_path / 'ticks' / day
    d.mkdir(parents=True)
    bars = [b for b in breakout_session() if not ('09:50' <= b['ts'][11:16] < '09:56')]
    (d / 'NIFTYBEES.jsonl').write_text(''.join(json.dumps(b) + '\n' for b in bars))
    record = orb.finalize_day(day)
    assert record['blind'] is True
    assert orb.finalize_day(day) is None
    stored = json.loads((tmp_path / 'track.jsonl').read_text().strip())
    assert stored['blind'] is True and stored['arm'] == orb.ARM
