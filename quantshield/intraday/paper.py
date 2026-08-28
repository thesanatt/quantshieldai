import argparse
import json
import math
import os
import sys
import time
from datetime import datetime

import numpy as np

from quantshield.costs import round_trip_cost
from quantshield.intraday.candles import CANDLES_DIR, day_path
from quantshield.paths import DATA, INTRADAY
from quantshield.utils import append_jsonl, atomic_write_json, log, now_ist, read_jsonl

TICKS_DIR = str(INTRADAY / 'ticks')
STATE_PATH = str(INTRADAY / 'paper_state.json')
TRACK_PATH = str(INTRADAY / 'paper_track_record.jsonl')
KILL_PATH = str(DATA / 'KILL_INTRADAY')

ARM = 'ORB-NIFTYBEES-v1'
SYMBOL = 'NIFTYBEES'
TICK = 0.01
HALF_SPREAD = 0.02
NOTIONAL = 2000.0
OR_START = '09:15'
OR_END = '09:45'
ENTRY_DEADLINE = '13:00'
TIME_EXIT = '15:10'
SESSION_CLOSE = '15:30'
SESSION_MINUTES = 375.0
MIN_OR_BARS = 25
MAX_GAP_MIN = 3
POLL_S = 20


def load_bars(day: str, symbol: str = SYMBOL) -> list[dict]:
    merged: dict[str, dict] = {}
    for bar in read_jsonl(day_path(symbol, day, TICKS_DIR)) + read_jsonl(day_path(symbol, day, CANDLES_DIR)):
        merged[bar['ts'][:16]] = bar
    return [merged[k] for k in sorted(merged)]


def minute_of(bar: dict) -> str:
    return bar['ts'][11:16]


def opening_range(bars: list[dict]) -> dict | None:
    window = [b for b in bars if OR_START <= minute_of(b) < OR_END]
    if len(window) < MIN_OR_BARS:
        return None
    return {
        'high': max(b['high'] for b in window),
        'low': min(b['low'] for b in window),
        'bars': len(window),
    }


def levels(orb: dict) -> tuple[float, float]:
    trigger = math.ceil((orb['high'] + TICK) * 100) / 100
    stop = math.floor(((orb['high'] + orb['low']) / 2) * 100) / 100
    return trigger, stop


def max_gap_minutes(bars: list[dict], upto: str) -> int:
    stamps = np.array(sorted(b['ts'][:16] for b in bars if OR_START <= minute_of(b) <= upto), dtype='datetime64[m]')
    if stamps.size < 2:
        return 0
    return max(0, int(np.diff(stamps).astype(int).max()) - 1)


def is_blind(record: dict) -> bool:
    return record['signal_gap_min'] > MAX_GAP_MIN


def evaluate_session(bars: list[dict], day: str) -> dict | None:
    orb = opening_range(bars)
    if orb is None:
        return None
    trigger, stop = levels(orb)
    entry_px: float | None = None
    entry_ts: str | None = None
    exit_px: float | None = None
    exit_ts: str | None = None
    exit_reason: str | None = None
    qty = 0

    for bar in bars:
        m = minute_of(bar)
        if m < OR_END:
            continue
        if entry_px is None:
            if m >= ENTRY_DEADLINE:
                break
            if bar['high'] >= trigger:
                entry_px = round(trigger + TICK + HALF_SPREAD, 2)
                entry_ts = bar['ts']
                qty = int(NOTIONAL // entry_px)
                if bar['low'] <= stop:
                    exit_px = round(stop - HALF_SPREAD, 2)
                    exit_ts = bar['ts']
                    exit_reason = 'stop_same_bar'
                    break
            continue
        if bar['low'] <= stop:
            exit_px = round(stop - HALF_SPREAD, 2)
            exit_ts = bar['ts']
            exit_reason = 'stop'
            break
        if m >= TIME_EXIT:
            exit_px = round(bar['close'] - HALF_SPREAD, 2)
            exit_ts = bar['ts']
            exit_reason = 'time_exit'
            break

    session_bars = [b for b in bars if OR_START <= minute_of(b) <= SESSION_CLOSE]
    bench_open = session_bars[0]['close'] if session_bars else None
    bench_close = session_bars[-1]['close'] if session_bars else None
    bench_ret = (bench_close / bench_open - 1) if bench_open and bench_close else 0.0
    signal_minute = entry_ts[11:16] if entry_ts else ENTRY_DEADLINE

    record = {
        'date': day,
        'arm': ARM,
        'or_high': orb['high'],
        'or_low': orb['low'],
        'or_bars': orb['bars'],
        'trigger': trigger,
        'stop': stop,
        'triggered': entry_px is not None,
        'bench_open': bench_open,
        'bench_close': bench_close,
        'bench_ret_pct': round(bench_ret * 100, 4),
        'max_gap_min': max_gap_minutes(bars, TIME_EXIT),
        'signal_gap_min': max_gap_minutes(bars, signal_minute),
    }

    if entry_px is None:
        record.update({'qty': 0, 'gross': 0.0, 'costs': 0.0, 'net': 0.0,
                       'strat_ret_pct': 0.0, 'time_in_market_frac': 0.0})
        return record

    if exit_px is None:
        last = session_bars[-1] if session_bars else None
        exit_px = round(last['close'] - HALF_SPREAD, 2) if last else entry_px
        exit_ts = last['ts'] if last else entry_ts
        exit_reason = 'session_end'

    gross = qty * (exit_px - entry_px)
    costs = round_trip_cost(qty * entry_px, qty * exit_px, etf=True)
    net = gross - costs
    held_min = (datetime.fromisoformat(exit_ts) - datetime.fromisoformat(entry_ts)).total_seconds() / 60
    record.update({
        'entry_ts': entry_ts, 'entry_px': round(entry_px, 2),
        'exit_ts': exit_ts, 'exit_px': round(exit_px, 2), 'exit_reason': exit_reason,
        'qty': qty,
        'gross': round(gross, 2), 'costs': round(costs, 2), 'net': round(net, 2),
        'strat_ret_pct': round(net / NOTIONAL * 100, 4),
        'time_in_market_frac': round(max(held_min, 1) / SESSION_MINUTES, 4),
    })
    return record


def already_recorded(day: str) -> bool:
    return any(r.get('date') == day and r.get('arm') == ARM for r in read_jsonl(TRACK_PATH))


def append_record(record: dict) -> None:
    append_jsonl(TRACK_PATH, record)


def finalize_day(day: str) -> dict | None:
    if already_recorded(day):
        log(f'{day} already recorded', 'orb')
        return None
    bars = load_bars(day)
    record = evaluate_session(bars, day)
    if record is None:
        log(f'{day}: opening range incomplete ({len(bars)} bars); nothing recorded', 'orb')
        return None
    record['blind'] = is_blind(record)
    append_record(record)
    log(f"{day}: triggered={record['triggered']} net={record.get('net')} blind={record['blind']}", 'orb')
    return record


def run_live() -> int:
    day = now_ist().strftime('%Y-%m-%d')
    if already_recorded(day):
        log(f'{day} already recorded', 'orb')
        return 0
    while True:
        if os.path.exists(KILL_PATH):
            log('KILL_INTRADAY present; stopping', 'orb')
            return 2
        now = now_ist()
        bars = load_bars(day)
        state = {'date': day, 'updated': now.isoformat(), 'bars_seen': len(bars), 'phase': 'TRACKING'}
        orb = opening_range(bars)
        if orb:
            trigger, stop = levels(orb)
            state.update({'or_high': orb['high'], 'or_low': orb['low'], 'trigger': trigger, 'stop': stop})
        atomic_write_json(STATE_PATH, state)
        if now.strftime('%H:%M') >= TIME_EXIT:
            record = finalize_day(day)
            state['phase'] = 'DONE'
            atomic_write_json(STATE_PATH, state)
            return 0 if record else 1
        time.sleep(POLL_S)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--live', action='store_true')
    parser.add_argument('--replay', default=None)
    args = parser.parse_args()
    if args.replay:
        print(json.dumps(evaluate_session(load_bars(args.replay), args.replay), indent=2))
        return
    if args.live:
        sys.exit(run_live())
    record = finalize_day(now_ist().strftime('%Y-%m-%d'))
    print(json.dumps(record if record else {'ok': False, 'reason': 'nothing recorded'}))


if __name__ == '__main__':
    main()
