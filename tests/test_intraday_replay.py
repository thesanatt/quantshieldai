import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pytest

import quantshield.intraday.candles as candles
import quantshield.intraday.replay as replay
from quantshield.intraday import stats
from quantshield.intraday.paper import SYMBOL

REPO = Path(__file__).resolve().parent.parent


def bar(day: str, hh: int, mm: int, o: float, h: float, lo: float, c: float) -> dict:
    return {'ts': f'{day}T{hh:02d}:{mm:02d}:00', 'open': o, 'high': h, 'low': lo, 'close': c, 'volume': 1}


def session(day: str, breakout: bool, close: float = 101.0) -> list[dict]:
    bars = [bar(day, 9, 15 + i, 101.0, 102.0 if i == 10 else 101.2, 100.0 if i == 20 else 100.8, 101.0) for i in range(30)]
    h, m = 9, 45
    for i in range(345):
        if breakout and i == 15:
            bars.append(bar(day, h, m, 101.9, 102.5, 101.8, 102.4))
        else:
            px = close if i > 15 else 101.0
            bars.append(bar(day, h, m, px, px + 0.05, px - 0.05, px))
        m += 1
        if m == 60:
            m = 0
            h += 1
    return bars


def write_days(root: Path, days: dict[str, list[dict]]) -> None:
    for day, bars in days.items():
        candles.write_day(SYMBOL, day, bars, str(root))


def test_bootstrap_p_direction_and_determinism() -> None:
    assert stats.bootstrap_p([1.0, 2.0]) == 1.0
    assert stats.bootstrap_p([-1.0, -2.0, -0.5, -3.0]) == 1.0
    assert stats.bootstrap_p([1.0, 2.0, 0.5, 3.0]) == 0.0
    mixed = [0.4, -0.1, 0.3, -0.2, 0.5, 0.1, -0.05, 0.2]
    assert stats.bootstrap_p(mixed) == stats.bootstrap_p(np.array(mixed))
    assert 0.0 < stats.bootstrap_p(mixed) < 0.5
    assert 'one-sided' in stats.BOOTSTRAP_DESCRIPTION and 'percentile bootstrap' in stats.BOOTSTRAP_DESCRIPTION


def test_adjusted_deltas_matches_scalar_formula() -> None:
    rows = [{'strat_ret_pct': 0.3, 'time_in_market_frac': 0.5, 'bench_ret_pct': -0.2},
            {'strat_ret_pct': 0.0, 'time_in_market_frac': 0.0, 'bench_ret_pct': 1.1}]
    out = stats.adjusted_deltas(rows)
    assert out.tolist() == [0.3 - 0.5 * -0.2, 0.0]
    assert stats.adjusted_deltas([]).size == 0


def test_buy_and_hold_uses_first_open_and_last_close() -> None:
    rows = [{'date': '2026-01-06', 'bench_open': 110.0, 'bench_close': 120.0},
            {'date': '2026-01-05', 'bench_open': 100.0, 'bench_close': 105.0}]
    assert stats.buy_and_hold_pct(rows) == pytest.approx(20.0)
    assert stats.buy_and_hold_pct([]) is None
    assert stats.buy_and_hold_pct([{'date': '2026-01-05'}]) is None


def test_to_bar_drops_timezone_and_defaults_volume() -> None:
    stamp = datetime(2026, 7, 21, 9, 15, tzinfo=UTC)
    out = candles.to_bar({'date': stamp, 'open': 1.0, 'high': 2.0, 'low': 0.5, 'close': 1.5})
    assert out == {'ts': '2026-07-21T09:15:00', 'open': 1.0, 'high': 2.0, 'low': 0.5, 'close': 1.5, 'volume': 0}


def test_write_and_read_day_roundtrip(tmp_path: Path) -> None:
    bars = session('2026-07-21', False)
    path = candles.write_day(SYMBOL, '2026-07-21', bars, str(tmp_path))
    assert path == str(tmp_path / '2026-07-21' / f'{SYMBOL}.jsonl')
    assert candles.read_day(SYMBOL, '2026-07-21', str(tmp_path)) == bars
    assert candles.read_day(SYMBOL, '2026-07-22', str(tmp_path)) == []


class FakeKite:
    def __init__(self) -> None:
        self.instrument_calls = 0
        self.history_calls: list[tuple[int, datetime, datetime]] = []

    def instruments(self, exchange: str) -> list[dict]:
        self.instrument_calls += 1
        return [{'tradingsymbol': 'NIFTYBEES', 'instrument_token': 2707457}]

    def historical_data(self, token: int, start: datetime, end: datetime, interval: str) -> list[dict]:
        self.history_calls.append((token, start, end))
        return [{'date': datetime(2026, 7, 21, 9, 15, tzinfo=UTC), 'open': 1, 'high': 2, 'low': 0.5, 'close': 1.5, 'volume': 3}]


def test_instrument_token_cached_per_run(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(candles, '_INSTRUMENTS', {})
    kite = FakeKite()
    assert candles.instrument_token(kite, 'NIFTYBEES') == 2707457
    assert candles.instrument_token(kite, 'SBIN') is None
    assert kite.instrument_calls == 1


def test_fetch_minute_bars_chunks_and_groups_by_day(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(candles.time, 'sleep', lambda s: None)
    kite = FakeKite()
    start = datetime(2026, 1, 1)
    end = datetime(2026, 5, 1)
    by_day = candles.fetch_minute_bars(kite, 2707457, start, end)
    assert len(kite.history_calls) == 3
    assert kite.history_calls[0][1] == start and kite.history_calls[-1][2] == end
    assert list(by_day) == ['2026-07-21']
    assert len(by_day['2026-07-21']) == 3


def test_aggregate_summary_fields() -> None:
    records = [
        {'date': '2026-01-05', 'triggered': True, 'net': 4.0, 'gross': 5.0, 'costs': 1.0, 'or_high': 102.0, 'or_low': 100.0,
         'entry_px': 102.04, 'stop': 101.0, 'qty': 19, 'strat_ret_pct': 0.2, 'time_in_market_frac': 0.5, 'bench_ret_pct': 0.1,
         'bench_open': 100.0, 'bench_close': 101.0},
        {'date': '2026-01-06', 'triggered': True, 'net': -6.0, 'gross': -5.0, 'costs': 1.0, 'or_high': 102.0, 'or_low': 100.0,
         'entry_px': 102.04, 'stop': 101.0, 'qty': 19, 'strat_ret_pct': -0.3, 'time_in_market_frac': 0.2, 'bench_ret_pct': -0.5,
         'bench_open': 101.0, 'bench_close': 99.0},
        {'date': '2026-01-07', 'triggered': False, 'net': 0.0, 'gross': 0.0, 'costs': 0.0, 'or_high': 101.0, 'or_low': 100.0,
         'strat_ret_pct': 0.0, 'time_in_market_frac': 0.0, 'bench_ret_pct': 0.2, 'bench_open': 99.0, 'bench_close': 110.0},
    ]
    s = replay.aggregate(records)
    assert s['sessions'] == 3 and s['triggered'] == 2 and s['wins'] == 1
    assert s['win_rate_pct'] == 50.0
    assert s['payoff_ratio'] == pytest.approx(4.0 / 6.0, abs=0.01)
    assert s['breakeven_win_rate_pct'] == pytest.approx(1 / (1 + 4.0 / 6.0) * 100, abs=0.1)
    assert s['gross_total_rs'] == 0.0 and s['net_total_rs'] == -2.0 and s['total_costs_rs'] == 2.0
    assert s['max_drawdown_rs'] == -6.0
    assert s['bench_cum_daily_pct'] == pytest.approx(-0.2)
    assert s['bench_hold_ret_pct'] == pytest.approx(10.0)
    assert s['cost_in_r_median'] == pytest.approx(1.0 / (1.04 * 19), abs=0.001)
    assert s['bench_open_definition'] == '09:15 bar close'
    assert 0.0 < s['bootstrap_p_one_sided'] < 1.0


def test_aggregate_empty() -> None:
    s = replay.aggregate([])
    assert s['sessions'] == 0 and s['date_range'] == [] and s['win_rate_pct'] is None
    assert s['bootstrap_p_one_sided'] == 1.0


def test_replay_reads_candles_dir_and_respects_window(tmp_path: Path) -> None:
    write_days(tmp_path, {
        '2026-07-20': session('2026-07-20', True, close=103.0),
        '2026-07-21': session('2026-07-21', False),
        '2026-07-22': session('2026-07-22', False)[:10],
        '2026-07-23': session('2026-07-23', True, close=100.5),
    })
    out = replay.replay(str(tmp_path), '2026-07-20', '2026-07-22')
    assert [r['date'] for r in out['records']] == ['2026-07-20', '2026-07-21']
    assert out['summary']['skipped_days'] == ['2026-07-22']
    assert out['summary']['triggered'] == 1
    assert out['records'][0]['net'] > 0
    assert replay.session_days(str(tmp_path / 'missing'), '2000-01-01', '2099-01-01') == []


def test_cli_writes_out_and_amends_only_with_flag(tmp_path: Path) -> None:
    write_days(tmp_path / 'candles', {'2026-07-20': session('2026-07-20', True, close=103.0)})
    gate = tmp_path / 'gate.json'
    gate.write_text(json.dumps({'registered': '2026-07-21T11:40:00+05:30', 'status': 'CLOSED', 'amendments': []}))
    out = tmp_path / 'replay.json'
    base = [sys.executable, '-m', 'quantshield.intraday.replay', '--candles-dir', str(tmp_path / 'candles'),
            '--end', '2026-07-20', '--out', str(out), '--gate', str(gate)]
    result = subprocess.run(base, capture_output=True, text=True, cwd=str(REPO))
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)['sessions'] == 1
    assert json.loads(out.read_text())['summary']['triggered'] == 1
    assert json.loads(gate.read_text())['amendments'] == []
    result = subprocess.run(base + ['--amend'], capture_output=True, text=True, cwd=str(REPO))
    assert result.returncode == 0, result.stderr
    amendments = json.loads(gate.read_text())['amendments']
    assert len(amendments) == 1 and amendments[0]['type'] == 'verification'
    assert amendments[0]['results']['sessions'] == 1


def test_dashboard_card_shape() -> None:
    out = replay.replay(str(REPO / 'nonexistent'), '2000-01-01', '2099-01-01')
    card = replay.dashboard_card(out, {'registered': '2026-07-21T11:40:00+05:30', 'status': 'CLOSED'})
    assert set(card) == {'registered', 'sessions', 'triggered', 'wins', 'win_rate_pct', 'breakeven_win_rate_pct', 'gross',
                         'costs', 'net', 'max_drawdown', 'bootstrap_p', 'notional', 'verdict', 'benchmark_note'}
    assert card['registered'] == '2026-07-21'
    assert card['notional'] == 2000
    assert 'closed' in card['verdict'].lower()


def test_committed_replay_and_card_agree() -> None:
    saved = json.loads((REPO / 'data' / 'intraday' / 'orb_replay.json').read_text())
    card = json.loads((REPO / 'dashboard' / 'src' / 'data' / 'orb.json').read_text())
    s = replay.aggregate(saved['records'])
    for key in ('sessions', 'triggered', 'wins', 'net_total_rs', 'bench_cum_daily_pct', 'bootstrap_p_one_sided'):
        assert s[key] == saved['summary'][key]
    assert (card['sessions'], card['triggered'], card['wins'], card['net']) == (s['sessions'], s['triggered'], s['wins'], s['net_total_rs'])
    assert all(r['bench_open'] is not None for r in saved['records'])
