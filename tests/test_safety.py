import os
from pathlib import Path

import quantshield.broker.alpaca as alpaca
import quantshield.broker.zerodha as zerodha
import quantshield.intraday.feed as feed
import quantshield.intraday.paper as paper
import quantshield.intraday.scoreboard as scoreboard
import quantshield.live.daemon as daemon
import quantshield.live.executor as executor
import quantshield.live.export as export
import quantshield.live.planner as planner
from quantshield import paths
from quantshield.research import track_record
from tests.conftest import GUARDED_DIRS, REPO_ROOT, TEST_ROOT, TEST_ROOT_SUBDIRS, describe_changes, tree_snapshot

MODULE_PATHS = [
    alpaca.TRADE_LOG_PATH, alpaca.POSITIONS_PATH, alpaca.DEFAULT_WEIGHTS_PATH,
    zerodha.ACCESS_TOKEN_PATH,
    feed.TICKS_DIR, feed.HEARTBEAT_PATH,
    paper.STATE_PATH, paper.TRACK_PATH, paper.KILL_PATH,
    scoreboard.TRACK_PATH, scoreboard.GATE_PATH, scoreboard.OUT_PATH,
    daemon.HEARTBEAT_PATH, daemon.EMERGENCY_PATH, daemon.SMALL_PLAN_PATH, daemon.SMALL_TRACK_PATH,
    executor.PLAN_PATH, executor.STATE_PATH, executor.JOURNAL_PATH, executor.TRADE_LOG_PATH,
    executor.KILL_FILE, executor.LOCK_PATH,
    export.OUT_PATH, export.STATE_PATH, export.HEARTBEAT_PATH,
    planner.STATE_PATH, planner.PLAN_PATH, planner.TRACK_PATH,
    str(track_record.TRACK_RECORD_PATH), str(track_record.SNAPSHOTS_DIR),
]


def test_root_is_redirected_to_a_temporary_directory() -> None:
    assert os.environ['QUANTSHIELD_ROOT'] == str(TEST_ROOT)
    assert paths.ROOT.resolve() == TEST_ROOT
    assert TEST_ROOT != REPO_ROOT
    assert REPO_ROOT not in TEST_ROOT.parents
    for name in ('DATA', 'PORTFOLIO', 'MONITOR', 'INTRADAY', 'JOURNAL', 'RESEARCH', 'DASHBOARD'):
        assert TEST_ROOT in getattr(paths, name).resolve().parents, name


def test_temporary_root_has_the_data_layout() -> None:
    for sub in TEST_ROOT_SUBDIRS:
        assert (TEST_ROOT / sub).is_dir(), sub


def test_every_module_path_constant_lives_under_the_temporary_root() -> None:
    for raw in MODULE_PATHS:
        resolved = Path(raw).resolve()
        assert TEST_ROOT == resolved or TEST_ROOT in resolved.parents, raw
        assert REPO_ROOT not in resolved.parents, raw


def test_guarded_repo_dirs_are_untouched_so_far(guarded_repo_tree: dict[str, int]) -> None:
    assert any((REPO_ROOT / rel).exists() for rel in GUARDED_DIRS)
    assert describe_changes(guarded_repo_tree, tree_snapshot()) == []


def test_change_detector_reports_creates_deletes_and_modifications() -> None:
    before = {'a': 1, 'b': 2, 'c': 3}
    after = {'a': 1, 'b': 5, 'd': 4}
    assert describe_changes(before, after) == ['created: d', 'deleted: c', 'modified: b']
    assert describe_changes(before, dict(before)) == []
