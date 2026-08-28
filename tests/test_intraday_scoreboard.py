import json
from pathlib import Path

import pytest

import quantshield.intraday.scoreboard as sb

PRIMARY = 'ORB-NIFTYBEES-v1'


def rec(date: str, triggered: bool, net: float, bench: float, tim: float, blind: bool = False,
        arm: str = PRIMARY, bench_open: float = 100.0, bench_close: float = 101.0) -> dict:
    return {'date': date, 'arm': arm, 'triggered': triggered, 'net': net, 'costs': 1.5 if triggered else 0.0,
            'strat_ret_pct': net / 20.0, 'bench_ret_pct': bench, 'time_in_market_frac': tim, 'blind': blind,
            'bench_open': bench_open, 'bench_close': bench_close}


def day(i: int) -> str:
    return f'2026-{1 + i // 28:02d}-{1 + i % 28:02d}'


def setup(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, rows: list[dict], primary: str = PRIMARY) -> None:
    track = tmp_path / 'track.jsonl'
    track.write_text(''.join(json.dumps(r) + '\n' for r in rows))
    gate = tmp_path / 'gate.json'
    gate.write_text(json.dumps({'primary_hypothesis': {'name': primary}, 'benchmark_and_test': {'min_sessions': 60}}))
    monkeypatch.setattr(sb, 'TRACK_PATH', str(track))
    monkeypatch.setattr(sb, 'GATE_PATH', str(gate))


def test_empty_track(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    setup(tmp_path, monkeypatch, [])
    board = sb.build()
    assert board['arms'] == {}
    assert board['gate']['status'] == 'CLOSED'
    assert board['gate']['primary_arm'] == PRIMARY
    assert 'bootstrap' in board['gate']['test']


def test_gate_terms_read_from_committed_gate_file(repo_root: Path) -> None:
    terms = sb.gate_terms(str(repo_root / 'data' / 'intraday' / 'gate.json'))
    assert terms['primary_arm'] == PRIMARY
    assert terms['min_sessions'] == 60
    assert terms['p_threshold'] == 0.05


def test_gate_terms_fall_back_when_gate_file_is_missing(tmp_path: Path) -> None:
    terms = sb.gate_terms(str(tmp_path / 'absent.json'))
    assert terms == {'primary_arm': None, 'min_sessions': 60, 'p_threshold': 0.05}


def test_blind_sessions_excluded(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    setup(tmp_path, monkeypatch, [rec('2026-07-21', True, 5.0, 0.1, 0.5),
                                  rec('2026-07-22', True, -3.0, 0.2, 0.5, blind=True)])
    s = sb.build()['arms'][PRIMARY]
    assert s['sessions_scored'] == 1
    assert s['sessions_blind'] == 1
    assert s['net_total_rs'] == pytest.approx(5.0)
    assert s['bootstrap_p_one_sided'] is None


def test_gate_closed_below_min_sessions(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    setup(tmp_path, monkeypatch, [rec(f'2026-07-{d:02d}', True, 10.0, 0.1, 0.5) for d in range(1, 21)])
    s = sb.build()['arms'][PRIMARY]
    assert s['sessions_remaining_for_gate'] == 40
    assert s['gate_open'] is False


def test_directional_guard_uses_buy_and_hold_not_session_sum(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    rows = [rec(day(d), True, 8.0, 0.3, 0.5, bench_open=100.0 - d * 0.5, bench_close=100.5 - d * 0.5) for d in range(70)]
    setup(tmp_path, monkeypatch, rows)
    s = sb.build()['arms'][PRIMARY]
    assert s['sessions_scored'] == 70
    assert s['bootstrap_p_one_sided'] < 0.05
    assert s['bench_hold_ret_pct'] == pytest.approx((66.0 / 100.0 - 1) * 100, abs=0.01)
    assert s['directional_guard_ok'] is False
    assert s['gate_open'] is False


def test_directional_guard_missing_prices_fails_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    rows = [rec(day(d), True, 8.0, 0.3, 0.5) for d in range(70)]
    for r in rows:
        r.pop('bench_open')
        r.pop('bench_close')
    setup(tmp_path, monkeypatch, rows)
    s = sb.build()['arms'][PRIMARY]
    assert s['bench_hold_ret_pct'] is None
    assert s['directional_guard_ok'] is False
    assert s['gate_open'] is False


def test_gate_opens_on_all_criteria(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    rows = [rec(day(d), True, 8.0, 0.3, 0.5, bench_open=100.0 + d * 0.1, bench_close=100.1 + d * 0.1) for d in range(70)]
    setup(tmp_path, monkeypatch, rows)
    board = sb.build()
    s = board['arms'][PRIMARY]
    assert s['directional_guard_ok'] is True
    assert s['bootstrap_p_one_sided'] < 0.05
    assert s['gate_open'] is True
    assert board['gate']['status'] == 'OPEN'


def test_only_primary_arm_can_open_gate(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    rows = [rec(day(d), True, 8.0, 0.3, 0.5, arm='ORB-NIFTYBEES-v2', bench_open=100.0, bench_close=110.0) for d in range(70)]
    setup(tmp_path, monkeypatch, rows)
    board = sb.build()
    s = board['arms']['ORB-NIFTYBEES-v2']
    assert s['primary'] is False
    assert s['directional_guard_ok'] is True
    assert s['bootstrap_p_one_sided'] < 0.05
    assert s['gate_open'] is False
    assert board['gate']['status'] == 'CLOSED'


def test_primary_name_follows_gate_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    rows = [rec(day(d), True, 8.0, 0.3, 0.5, arm='ORB-NIFTYBEES-v2', bench_open=100.0, bench_close=110.0) for d in range(70)]
    setup(tmp_path, monkeypatch, rows, primary='ORB-NIFTYBEES-v2')
    board = sb.build()
    assert board['arms']['ORB-NIFTYBEES-v2']['gate_open'] is True
    assert board['gate']['status'] == 'OPEN'


def test_arms_grouped_separately(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    setup(tmp_path, monkeypatch, [rec('2026-07-21', True, 5.0, 0.1, 0.5),
                                  rec('2026-07-21', True, -2.0, 0.1, 0.3, arm='discretionary')])
    arms = sb.build()['arms']
    assert set(arms) == {PRIMARY, 'discretionary'}
    assert arms[PRIMARY]['primary'] is True
    assert arms['discretionary']['primary'] is False
