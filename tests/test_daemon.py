import json
import os
import subprocess
from datetime import UTC, date, datetime, timedelta
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest
import pytz

import quantshield.broker.zerodha as zerodha
import quantshield.live.daemon as daemon

IST = pytz.timezone('Asia/Kolkata')


def freeze(monkeypatch: pytest.MonkeyPatch, y: int, m: int, d: int, hh: int, mm: int) -> datetime:
    frozen = IST.localize(datetime(y, m, d, hh, mm))

    class FakeDatetime(datetime):
        @classmethod
        def now(cls, tz: object = None) -> datetime:
            return frozen if tz is None else frozen.astimezone(tz)

    monkeypatch.setattr(daemon, 'datetime', FakeDatetime)
    return frozen


@pytest.fixture
def paths(tmp_path: object, monkeypatch: pytest.MonkeyPatch) -> object:
    for name in ('HEARTBEAT_PATH', 'EMERGENCY_PATH', 'EMERGENCY_LOG_PATH', 'LOGIN_NOTIFY_PATH',
                 'SNAPSHOT_MARKER_PATH', 'SMALL_TRACK_PATH', 'SMALL_PLAN_PATH', 'SMALL_EXEC_JOURNAL_PATH',
                 'FEED_HEARTBEAT_PATH', 'FEED_STALE_NOTIFY_PATH'):
        monkeypatch.setattr(daemon, name, str(tmp_path / name.lower()))
    monkeypatch.setattr(zerodha, 'ACCESS_TOKEN_PATH', str(tmp_path / 'token.json'))
    monkeypatch.setenv('KITE_API_KEY', 'dummy')
    return tmp_path


def write(path: str, data: object) -> None:
    with open(path, 'w') as f:
        json.dump(data, f)


def today_ist() -> str:
    return datetime.now(IST).strftime('%Y-%m-%d')


def fresh_token() -> None:
    write(zerodha.ACCESS_TOKEN_PATH, {'date': today_ist(), 'access_token': 'x'})


def today_plan(orders: list[dict]) -> str:
    gen = datetime.now(IST).replace(tzinfo=None).isoformat()
    write(daemon.SMALL_PLAN_PATH, {'generated': gen, 'orders': orders})
    return gen


ORDER = [{'action': 'BUY', 'symbol': 'SBIN.NS', 'qty': 1, 'ref_price': 1000.0}]


class TestCalendarReexports:
    def test_india_holiday_importable_from_daemon(self) -> None:
        assert daemon.is_india_holiday(date(2026, 1, 26)) is True
        assert daemon.is_india_holiday(date(2026, 10, 2)) is True
        assert daemon.is_india_holiday(date(2026, 3, 15)) is False

    def test_india_market_hours_gate(self) -> None:
        assert daemon.is_india_market_hours(IST.localize(datetime(2026, 7, 20, 10, 0))) is True
        assert daemon.is_india_market_hours(IST.localize(datetime(2026, 7, 20, 9, 14))) is False
        assert daemon.is_india_market_hours(IST.localize(datetime(2026, 7, 20, 15, 31))) is False
        assert daemon.is_india_market_hours(IST.localize(datetime(2026, 7, 18, 10, 0))) is False
        assert daemon.is_india_market_hours(IST.localize(datetime(2026, 1, 26, 10, 0))) is False

    def test_no_us_half_left(self) -> None:
        assert not hasattr(daemon, 'is_us_market_hours')
        assert not hasattr(daemon, 'US_HOLIDAYS')
        assert not hasattr(daemon, '_rate_limit')
        assert not hasattr(daemon, 'YFINANCE_MIN_INTERVAL')


class TestRetry:
    def test_first_try(self) -> None:
        assert daemon._retry_yfinance(lambda: 'ok') == 'ok'

    def test_second_try(self) -> None:
        attempts = [0]

        def flaky() -> str:
            attempts[0] += 1
            if attempts[0] < 2:
                raise ConnectionError('fail')
            return 'ok'

        with patch('quantshield.live.daemon.time.sleep') as sleep:
            assert daemon._retry_yfinance(flaky) == 'ok'
        sleep.assert_called_once_with(daemon.RETRY_BACKOFF)

    def test_exhausted_raises_after_three(self) -> None:
        attempts = [0]

        def always_fail() -> None:
            attempts[0] += 1
            raise RuntimeError('down')

        with patch('quantshield.live.daemon.time.sleep'):
            with pytest.raises(RuntimeError):
                daemon._retry_yfinance(always_fail)
        assert attempts[0] == 3


def close_frame(end: str = '2026-08-28') -> pd.DataFrame:
    idx = pd.bdate_range(end=end, periods=5)
    cols = {t: np.linspace(100, 104, 5) for t in daemon.INDIA_TICKERS}
    cols['SBIN.NS'] = np.array([100, 101, 102, 100, 94.0])
    cols['^VIX'] = np.array([15, 16, 17, np.nan, 18.5])
    cols['^INDIAVIX'] = np.array([12, 12.5, 13, 13.2, np.nan])
    cols['ITC.NS'] = np.array([50, 51, np.nan, np.nan, np.nan])
    return pd.DataFrame(cols, index=idx)


class TestStaleTickers:
    def test_flags_only_old_or_missing_columns(self) -> None:
        close = close_frame()
        close['DEAD.NS'] = np.nan
        assert daemon.stale_tickers(close, date(2026, 8, 28)) == ['ITC.NS', 'DEAD.NS']

    def test_tz_aware_index(self) -> None:
        close = close_frame()
        close.index = close.index.tz_localize('Asia/Kolkata')
        assert daemon.stale_tickers(close, date(2026, 8, 28)) == ['ITC.NS']

    def test_empty_frame(self) -> None:
        assert daemon.stale_tickers(pd.DataFrame(), date(2026, 8, 28)) == []


class TestFetchMarketData:
    def test_single_batched_download_and_vectorised_changes(self, monkeypatch: pytest.MonkeyPatch) -> None:
        calls: list[tuple] = []
        frame = close_frame()
        frame.columns = pd.MultiIndex.from_product([['Close'], frame.columns])

        def fake_download(tickers: list[str], **kwargs: object) -> pd.DataFrame:
            calls.append((tuple(tickers), kwargs))
            return frame

        fake_yf = MagicMock(download=fake_download)
        monkeypatch.setitem(__import__('sys').modules, 'yfinance', fake_yf)
        data = daemon.fetch_market_data()
        assert len(calls) == 1
        assert set(calls[0][0]) == {'^VIX', '^INDIAVIX', *daemon.INDIA_TICKERS}
        assert calls[0][1]['period'] == '5d'
        assert data['us_vix'] == 18.5
        assert data['india_vix'] == 13.2
        assert data['daily_changes']['SBIN.NS'] == -6.0
        assert 'ITC.NS' not in data['daily_changes']
        assert '^VIX' not in data['daily_changes']

    def test_retries_wrap_the_single_call(self, monkeypatch: pytest.MonkeyPatch) -> None:
        attempts = [0]

        def flaky(*a: object, **k: object) -> pd.DataFrame:
            attempts[0] += 1
            if attempts[0] < 3:
                raise ConnectionError('blip')
            return close_frame()

        monkeypatch.setitem(__import__('sys').modules, 'yfinance', MagicMock(download=flaky))
        with patch('quantshield.live.daemon.time.sleep'):
            data = daemon.fetch_market_data()
        assert attempts[0] == 3
        assert data['us_vix'] == 18.5

    def test_empty_download_yields_no_data(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setitem(__import__('sys').modules, 'yfinance', MagicMock(download=lambda *a, **k: pd.DataFrame()))
        data = daemon.fetch_market_data()
        assert daemon._no_data(data)


class TestCheckTriggers:
    def test_us_vix_threshold(self) -> None:
        assert daemon.check_triggers({'us_vix': 45.0, 'india_vix': None, 'daily_changes': {}})[0]
        assert not daemon.check_triggers({'us_vix': 20.0, 'india_vix': None, 'daily_changes': {}})[0]

    def test_india_vix_threshold(self) -> None:
        triggers, _ = daemon.check_triggers({'us_vix': None, 'india_vix': 35.0, 'daily_changes': {}})
        assert any('India VIX' in t for t in triggers)
        assert not daemon.check_triggers({'us_vix': None, 'india_vix': 15.0, 'daily_changes': {}})[0]

    def test_daily_drop(self) -> None:
        triggers, affected = daemon.check_triggers(
            {'us_vix': None, 'india_vix': None, 'daily_changes': {'SBIN.NS': -6.0, 'TCS.NS': -2.0}})
        assert affected == ['SBIN.NS']
        assert triggers == ['SBIN.NS down -6.0% today']

    def test_multiple_and_null(self) -> None:
        triggers, affected = daemon.check_triggers({'us_vix': 50.0, 'india_vix': 35.0, 'daily_changes': {'LT.NS': -7.0}})
        assert len(triggers) == 3 and affected == ['LT.NS']
        assert daemon.check_triggers({'us_vix': None, 'india_vix': None, 'daily_changes': {}}) == ([], [])


class TestHeartbeatAndEmergency:
    def test_heartbeat_all_clear(self, paths: object) -> None:
        hb = daemon.write_heartbeat({'us_vix': 18.0, 'india_vix': 14.0})
        assert hb['status'] == 'all_clear' and hb['us_vix'] == 18.0 and hb['timestamp']
        assert json.load(open(daemon.HEARTBEAT_PATH)) == hb

    def test_heartbeat_error(self, paths: object) -> None:
        daemon._write_heartbeat_error('NETWORK_ERROR', 'connection refused')
        data = json.load(open(daemon.HEARTBEAT_PATH))
        assert data['status'] == 'NETWORK_ERROR'
        assert 'connection refused' in data['error']
        assert data['us_vix'] is None and data['india_vix'] is None

    def test_emergency_file_and_log_append(self, paths: object) -> None:
        write(daemon.EMERGENCY_LOG_PATH, [{'old': True}])
        em = daemon.write_emergency(['VIX > 40'], ['SBIN.NS'], {'us_vix': 45.0, 'india_vix': None})
        assert em['active'] is True and em['affected_tickers'] == ['SBIN.NS']
        assert json.load(open(daemon.EMERGENCY_PATH)) == em
        elog = json.load(open(daemon.EMERGENCY_LOG_PATH))
        assert len(elog) == 2 and elog[0] == {'old': True} and elog[1]['active'] is True

    def test_emergency_log_created_or_repaired(self, paths: object) -> None:
        daemon.write_emergency(['t'], [], {'us_vix': 50})
        assert len(json.load(open(daemon.EMERGENCY_LOG_PATH))) == 1
        with open(daemon.EMERGENCY_LOG_PATH, 'w') as f:
            f.write('not json')
        daemon.write_emergency(['t'], [], {'us_vix': 50})
        assert len(json.load(open(daemon.EMERGENCY_LOG_PATH))) == 1


class TestSnapshotSchedule:
    def test_due_after_1535_on_trading_day(self, paths: object, monkeypatch: pytest.MonkeyPatch) -> None:
        freeze(monkeypatch, 2026, 7, 20, 15, 34)
        assert daemon.small_snapshot_due() is False
        freeze(monkeypatch, 2026, 7, 20, 15, 35)
        assert daemon.small_snapshot_due() is True
        freeze(monkeypatch, 2026, 7, 20, 16, 0)
        assert daemon.small_snapshot_due() is True

    def test_skips_weekend_and_holiday(self, paths: object, monkeypatch: pytest.MonkeyPatch) -> None:
        for y, m, d in ((2026, 7, 18), (2026, 7, 19), (2026, 1, 26)):
            freeze(monkeypatch, y, m, d, 16, 0)
            assert daemon.small_snapshot_due() is False

    def test_once_per_day_via_track_record(self, paths: object, monkeypatch: pytest.MonkeyPatch) -> None:
        freeze(monkeypatch, 2026, 7, 20, 16, 0)
        assert daemon.small_snapshot_due() is True
        write(daemon.SMALL_TRACK_PATH, {'inception': {}, 'snapshots': [{'date': '2026-07-20'}]})
        assert daemon.small_snapshot_due() is False
        write(daemon.SMALL_TRACK_PATH, {'inception': {}, 'snapshots': [{'date': '2026-07-17'}]})
        assert daemon.small_snapshot_due() is True

    def test_at_most_two_attempts_per_day(self, paths: object, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(daemon, 'token_fresh', lambda: True)
        freeze(monkeypatch, 2026, 7, 20, 16, 0)
        runs: list[list[str]] = []
        monkeypatch.setattr(daemon.subprocess, 'run', lambda cmd, **k: runs.append(cmd) or MagicMock(returncode=1))
        for _ in range(4):
            if daemon.small_snapshot_due():
                daemon.run_small_snapshot()
        assert len(runs) == 2
        freeze(monkeypatch, 2026, 7, 21, 16, 0)
        assert daemon.small_snapshot_due() is True

    def test_run_snapshot_invokes_planner_with_timeout(self, paths: object, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(daemon, 'token_fresh', lambda: True)
        calls: list[tuple] = []
        monkeypatch.setattr(daemon.subprocess, 'run', lambda cmd, **k: calls.append((cmd, k)) or MagicMock(returncode=0))
        daemon.run_small_snapshot()
        cmd, kwargs = calls[0]
        assert cmd[1:] == ['-m', daemon.SMALL_ENGINE_MODULE, '--snapshot']
        assert kwargs['timeout'] == 300

    def test_run_snapshot_survives_failure(self, paths: object, monkeypatch: pytest.MonkeyPatch,
                                           capsys: pytest.CaptureFixture) -> None:
        monkeypatch.setattr(daemon, 'token_fresh', lambda: True)
        def boom(*a: object, **k: object) -> None:
            raise OSError('exec failed')

        monkeypatch.setattr(daemon.subprocess, 'run', boom)
        daemon.run_small_snapshot()
        assert 'snapshot failed' in capsys.readouterr().err
        monkeypatch.setattr(daemon.subprocess, 'run', lambda *a, **k: MagicMock(returncode=3))
        daemon.run_small_snapshot()
        assert 'exited 3' in capsys.readouterr().err


class TestTradingWindow:
    def test_bounds(self, monkeypatch: pytest.MonkeyPatch) -> None:
        cases = [
            ((2026, 7, 20, 9, 24), False),
            ((2026, 7, 20, 9, 25), True),
            ((2026, 7, 20, 14, 30), True),
            ((2026, 7, 20, 14, 31), False),
            ((2026, 7, 18, 11, 0), False),
            ((2026, 1, 26, 11, 0), False),
        ]
        for args, expected in cases:
            freeze(monkeypatch, *args)
            assert daemon.small_trading_window() is expected, args


class TestRunSmallTrading:
    @pytest.fixture(autouse=True)
    def window(self, paths: object, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(daemon, 'small_trading_window', lambda: True)

    def test_outside_window_noop(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(daemon, 'small_trading_window', lambda: False)
        with patch('quantshield.live.daemon.subprocess.run') as run:
            daemon.run_small_trading()
            run.assert_not_called()

    def test_token_stale_notifies_once_and_skips(self) -> None:
        with patch('quantshield.live.daemon.subprocess.run') as run, \
             patch('quantshield.live.daemon.notify') as notify:
            daemon.run_small_trading()
            daemon.run_small_trading()
            run.assert_not_called()
            notify.assert_called_once()
            assert notify.call_args[0][0] == 'Zerodha access token expired; run the daily login before 09:25 IST'

    def test_generates_plan_then_executes(self) -> None:
        fresh_token()
        calls: list[list[str]] = []

        def fake_run(cmd: list[str], **kwargs: object) -> MagicMock:
            calls.append(cmd)
            if daemon.SMALL_ENGINE_MODULE in cmd:
                today_plan(ORDER)
            return MagicMock(returncode=0)

        with patch('quantshield.live.daemon.subprocess.run', side_effect=fake_run):
            daemon.run_small_trading()
        assert [c[2] for c in calls] == [daemon.SMALL_ENGINE_MODULE, daemon.SMALL_EXECUTE_MODULE]
        assert calls[1][1:] == ['-m', daemon.SMALL_EXECUTE_MODULE]

    def test_plan_today_no_orders_skips_execute(self) -> None:
        fresh_token()
        today_plan([])
        with patch('quantshield.live.daemon.subprocess.run') as run:
            daemon.run_small_trading()
            run.assert_not_called()

    def test_journal_entry_today_blocks_execute(self) -> None:
        fresh_token()
        gen = today_plan(ORDER)
        write(daemon.SMALL_EXEC_JOURNAL_PATH, [{'date': today_ist(), 'plan_generated': gen,
                                                'symbol': 'SBIN.NS', 'action': 'BUY', 'status': 'COMPLETE'}])
        with patch('quantshield.live.daemon.subprocess.run') as run:
            daemon.run_small_trading()
            run.assert_not_called()

    def test_journal_entry_blocks_even_for_regenerated_plan(self) -> None:
        fresh_token()
        today_plan(ORDER)
        write(daemon.SMALL_EXEC_JOURNAL_PATH, [{'date': today_ist(), 'plan_generated': '2026-01-01T09:30:00',
                                                'symbol': 'SBIN.NS', 'action': 'BUY', 'status': 'COMPLETE'}])
        with patch('quantshield.live.daemon.subprocess.run') as run:
            daemon.run_small_trading()
            run.assert_not_called()

    def test_stale_plan_regenerated_only_with_fresh_token(self) -> None:
        write(daemon.SMALL_PLAN_PATH, {'generated': '2020-01-01T10:00:00', 'orders': ORDER})
        with patch('quantshield.live.daemon.subprocess.run') as run, \
             patch('quantshield.live.daemon.notify') as notify:
            daemon.run_small_trading()
            run.assert_not_called()
            notify.assert_called_once()

    def test_token_rechecked_before_execute(self) -> None:
        today_plan(ORDER)
        with patch('quantshield.live.daemon.subprocess.run') as run, \
             patch('quantshield.live.daemon.notify') as notify:
            daemon.run_small_trading()
            run.assert_not_called()
            notify.assert_called_once()

    def test_plan_generation_failure_skips_execute(self) -> None:
        fresh_token()
        with patch('quantshield.live.daemon.subprocess.run', return_value=MagicMock(returncode=0)) as run:
            daemon.run_small_trading()
            assert run.call_count == 1
            assert daemon.SMALL_ENGINE_MODULE in run.call_args[0][0]

    def test_execute_uses_1500s_timeout(self) -> None:
        fresh_token()
        today_plan(ORDER)
        with patch('quantshield.live.daemon.subprocess.run', return_value=MagicMock(returncode=0)) as run:
            daemon.run_small_trading()
            assert run.call_args.kwargs['timeout'] == daemon.SMALL_EXECUTE_TIMEOUT == 1500

    @pytest.mark.parametrize('code', [2, 3, 4, 6])
    def test_self_notified_exit_codes_not_renotified(self, code: int) -> None:
        fresh_token()
        today_plan(ORDER)
        with patch('quantshield.live.daemon.subprocess.run', return_value=MagicMock(returncode=code)), \
             patch('quantshield.live.daemon.notify') as notify:
            daemon.run_small_trading()
            notify.assert_not_called()

    @pytest.mark.parametrize('code', [1, 5, 7])
    def test_other_nonzero_exits_notify(self, code: int) -> None:
        fresh_token()
        today_plan(ORDER)
        with patch('quantshield.live.daemon.subprocess.run', return_value=MagicMock(returncode=code)), \
             patch('quantshield.live.daemon.notify') as notify:
            daemon.run_small_trading()
            assert notify.call_count == 1
            assert f'exited {code}' in notify.call_args[0][0]

    def test_execute_timeout_notifies(self) -> None:
        fresh_token()
        today_plan(ORDER)
        with patch('quantshield.live.daemon.subprocess.run', side_effect=subprocess.TimeoutExpired('cmd', 1500)), \
             patch('quantshield.live.daemon.notify') as notify:
            daemon.run_small_trading()
            assert 'timed out' in notify.call_args[0][0]


class TestFeedFreshness:
    def test_fresh_heartbeat_silent(self, paths: object) -> None:
        write(daemon.FEED_HEARTBEAT_PATH, {'ts': datetime.now(UTC).isoformat()})
        with patch('quantshield.live.daemon.notify') as notify:
            daemon.check_feed_freshness()
            notify.assert_not_called()

    def test_stale_heartbeat_notifies_once_per_day(self, paths: object) -> None:
        write(daemon.FEED_HEARTBEAT_PATH, {'ts': (datetime.now(UTC) - timedelta(seconds=400)).isoformat()})
        with patch('quantshield.live.daemon.notify') as notify:
            daemon.check_feed_freshness()
            daemon.check_feed_freshness()
            assert notify.call_count == 1
            assert 'stale' in notify.call_args[0][0]

    def test_missing_or_bad_heartbeat_ignored(self, paths: object) -> None:
        with patch('quantshield.live.daemon.notify') as notify:
            daemon.check_feed_freshness()
            write(daemon.FEED_HEARTBEAT_PATH, {'ts': 'garbage'})
            daemon.check_feed_freshness()
            notify.assert_not_called()


class TestDeployDashboard:
    def test_invokes_script_with_timeout_and_logs_returncode(self, monkeypatch: pytest.MonkeyPatch,
                                                              capsys: pytest.CaptureFixture) -> None:
        calls: list[tuple] = []
        monkeypatch.setattr(daemon.subprocess, 'run',
                            lambda cmd, **k: calls.append((cmd, k)) or MagicMock(returncode=7, stderr='boom\n'))
        daemon.deploy_dashboard()
        cmd, kwargs = calls[0]
        assert cmd == [daemon.DEPLOY_SCRIPT]
        assert cmd[0].endswith('scripts/deploy_dashboard.sh')
        assert kwargs['timeout'] == 600
        err = capsys.readouterr().err
        assert 'exited 7' in err and 'boom' in err

    def test_failure_does_not_raise(self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture) -> None:
        def boom(*a: object, **k: object) -> None:
            raise OSError('missing')

        monkeypatch.setattr(daemon.subprocess, 'run', boom)
        daemon.deploy_dashboard()
        assert 'deploy failed' in capsys.readouterr().err


class TestRunCheck:
    @pytest.fixture
    def stubs(self, paths: object, monkeypatch: pytest.MonkeyPatch) -> dict:
        order: list[str] = []
        monkeypatch.setattr(daemon, 'run_small_trading', lambda: order.append('trade'))
        monkeypatch.setattr(daemon, 'run_small_snapshot', lambda: order.append('snapshot'))
        monkeypatch.setattr(daemon, 'deploy_dashboard', lambda: order.append('deploy'))
        monkeypatch.setattr(daemon, 'check_feed_freshness', lambda: order.append('feed'))
        monkeypatch.setattr(daemon, 'notify', lambda *a, **k: order.append('notify'))
        monkeypatch.setattr(daemon, 'fetch_market_data',
                            lambda: order.append('fetch') or {'us_vix': 15.0, 'india_vix': 12.0, 'daily_changes': {}})
        return {'order': order}

    def test_trading_runs_before_market_gate_only_with_auto_execute(self, stubs: dict, monkeypatch: pytest.MonkeyPatch) -> None:
        freeze(monkeypatch, 2026, 7, 20, 8, 0)
        daemon.run_check(auto_execute=False)
        assert stubs['order'] == []
        daemon.run_check(auto_execute=True)
        assert stubs['order'] == ['trade']

    def test_outside_hours_deploys_only_after_snapshot(self, stubs: dict, monkeypatch: pytest.MonkeyPatch) -> None:
        freeze(monkeypatch, 2026, 7, 20, 16, 0)
        daemon.run_check()
        assert stubs['order'] == ['snapshot', 'deploy']
        assert not os.path.exists(daemon.HEARTBEAT_PATH)

    def test_market_hours_full_sequence(self, stubs: dict, monkeypatch: pytest.MonkeyPatch) -> None:
        freeze(monkeypatch, 2026, 7, 20, 11, 0)
        daemon.run_check(auto_execute=True)
        assert stubs['order'] == ['trade', 'fetch', 'feed', 'deploy']
        assert json.load(open(daemon.HEARTBEAT_PATH))['status'] == 'all_clear'

    def test_emergency_path_writes_and_notifies(self, stubs: dict, monkeypatch: pytest.MonkeyPatch) -> None:
        freeze(monkeypatch, 2026, 7, 20, 11, 0)
        monkeypatch.setattr(daemon, 'fetch_market_data',
                            lambda: {'us_vix': 50.0, 'india_vix': 12.0, 'daily_changes': {'LT.NS': -8.0}})
        daemon.run_check()
        assert stubs['order'] == ['notify', 'feed', 'deploy']
        em = json.load(open(daemon.EMERGENCY_PATH))
        assert em['affected_tickers'] == ['LT.NS'] and len(em['triggers']) == 2

    def test_network_error_heartbeat_and_early_return(self, stubs: dict, monkeypatch: pytest.MonkeyPatch) -> None:
        freeze(monkeypatch, 2026, 7, 20, 11, 0)

        def down() -> None:
            raise ConnectionError('network down')

        monkeypatch.setattr(daemon, 'fetch_market_data', down)
        daemon.run_check()
        assert stubs['order'] == []
        assert json.load(open(daemon.HEARTBEAT_PATH))['status'] == 'NETWORK_ERROR'

    def test_no_data_heartbeat_instead_of_all_clear(self, stubs: dict, monkeypatch: pytest.MonkeyPatch) -> None:
        freeze(monkeypatch, 2026, 7, 20, 11, 0)
        monkeypatch.setattr(daemon, 'fetch_market_data', lambda: {'us_vix': None, 'india_vix': None, 'daily_changes': {}})
        daemon.run_check()
        assert json.load(open(daemon.HEARTBEAT_PATH))['status'] == 'NO_DATA'
        assert stubs['order'] == ['feed', 'deploy']

    def test_unexpected_exception_becomes_critical_heartbeat(self, stubs: dict, monkeypatch: pytest.MonkeyPatch) -> None:
        def boom() -> None:
            raise RuntimeError('boom')

        monkeypatch.setattr(daemon, 'small_snapshot_due', boom)
        daemon.run_check()
        assert json.load(open(daemon.HEARTBEAT_PATH))['status'] == 'CRITICAL_ERROR'


class TestMain:
    def test_once_and_auto_execute_flags(self, monkeypatch: pytest.MonkeyPatch) -> None:
        calls: list[bool] = []
        monkeypatch.setattr(daemon, 'run_check', lambda auto_execute=False: calls.append(auto_execute))
        monkeypatch.setattr(daemon.signal, 'signal', lambda *a: None)
        with patch('sys.argv', ['daemon', '--once', '--auto-execute']):
            daemon.main()
        assert calls == [True]
        with patch('sys.argv', ['daemon', '--once']):
            daemon.main()
        assert calls == [True, False]

    def test_loop_survives_exception_and_stops_on_shutdown(self, monkeypatch: pytest.MonkeyPatch) -> None:
        daemon._shutdown = False
        count = [0]

        def fake_run_check(auto_execute: bool = False) -> None:
            count[0] += 1
            daemon._shutdown = True
            raise RuntimeError('unexpected')

        monkeypatch.setattr(daemon, 'run_check', fake_run_check)
        monkeypatch.setattr(daemon, '_write_heartbeat_error', lambda *a: None)
        monkeypatch.setattr(daemon.signal, 'signal', lambda *a: None)
        with patch('quantshield.live.daemon.time.sleep'), patch('sys.argv', ['daemon', '--interval', '1']):
            daemon.main()
        assert count[0] == 1
        daemon._shutdown = False

    def test_signal_sets_shutdown(self) -> None:
        daemon._shutdown = False
        daemon._handle_signal(2, None)
        assert daemon._shutdown is True
        daemon._shutdown = False
