import json
import os
import sys

import numpy as np
import pandas as pd
import pytest

import quantshield.broker.zerodha as zerodha
import quantshield.live.planner as engine_small
from quantshield.config import INDIA_TICKERS
from quantshield.costs import delivery_cost as trade_cost
from quantshield.live.planner import CORE, build_plan


def make_scores(symbols: list[str]) -> pd.Series:
    vals = np.linspace(0.9, -0.9, len(symbols))
    return pd.Series(vals, index=symbols)


def make_ref(prices: dict[str, float]) -> pd.Series:
    return pd.Series(prices)


def empty_state() -> dict:
    return {'holdings': {}, 'cash': 0.0, 'updated': '2026-07-19T00:00:00'}


def test_integer_share_sizing() -> None:
    scores = make_scores(['S1', 'S2', 'S3'])
    ref = make_ref({CORE: 250.0, 'S1': 100.0, 'S2': 90.0, 'S3': 80.0})
    plan = build_plan(scores, ref, empty_state(), 5000.0, set(), 'risk_on')
    by_symbol = {o['symbol']: o for o in plan['orders']}
    assert by_symbol[CORE]['qty'] == 10
    assert by_symbol['S1']['qty'] == 12
    assert by_symbol['S2']['qty'] == 13
    for o in plan['orders']:
        assert isinstance(o['qty'], int)
        assert o['est_value'] == pytest.approx(o['qty'] * o['ref_price'], abs=0.01)
    assert 'S3' not in plan['target_portfolio']


def test_min_position_value_skip() -> None:
    scores = make_scores(['S1', 'S2', 'S3'])
    ref = make_ref({CORE: 250.0, 'S1': 700.0, 'S2': 100.0, 'S3': 90.0})
    plan = build_plan(scores, ref, empty_state(), 5000.0, set(), 'risk_on')
    symbols = [o['symbol'] for o in plan['orders']]
    assert 'S1' not in symbols
    assert 'S2' in symbols
    assert 'S3' in symbols


@pytest.mark.parametrize('price,expected_qty', [(800.0, 1), (400.0, 3), (799.99, 0), (630.0, 0)])
def test_min_trade_value_boundary_is_800(price: float, expected_qty: int) -> None:
    assert engine_small.MIN_TRADE_VALUE == 800.0
    scores = make_scores(['S1', 'S2'])
    ref = make_ref({CORE: 250.0, 'S1': price, 'S2': 100.0})
    plan = build_plan(scores, ref, empty_state(), 5000.0, set(), 'risk_on')
    buys = {o['symbol']: o for o in plan['orders'] if o['action'] == 'BUY'}
    assert buys[CORE]['qty'] == 10
    if expected_qty:
        assert buys['S1']['qty'] == expected_qty
        assert buys['S1']['est_value'] >= 800.0
    else:
        assert 'S1' not in buys
        assert 'S1' not in plan['target_portfolio']


def test_one_share_exceeds_slice_skip() -> None:
    scores = make_scores(['S1', 'S2', 'S3'])
    ref = make_ref({CORE: 250.0, 'S1': 1300.0, 'S2': 100.0, 'S3': 90.0})
    plan = build_plan(scores, ref, empty_state(), 5000.0, set(), 'risk_on')
    symbols = [o['symbol'] for o in plan['orders']]
    assert 'S1' not in symbols
    assert 'S2' in symbols
    assert 'S3' in symbols


def test_hysteresis_holds_rank_four() -> None:
    scores = make_scores(['S1', 'S2', 'S3', 'S4', 'S5'])
    ref = make_ref({CORE: 250.0, 'S1': 100.0, 'S2': 100.0, 'S3': 100.0, 'S4': 100.0, 'S5': 100.0})
    state = {'holdings': {'S4': 5}, 'cash': 0.0, 'updated': ''}
    plan = build_plan(scores, ref, state, 5000.0, set(), 'risk_on')
    actions = {(o['action'], o['symbol']) for o in plan['orders']}
    assert ('SELL', 'S4') not in actions
    assert 'S4' in plan['target_portfolio']
    assert 'S1' in plan['target_portfolio']


def test_hysteresis_replaces_below_rank_four_with_top_two() -> None:
    scores = make_scores(['S1', 'S2', 'S3', 'S4', 'S5'])
    ref = make_ref({CORE: 250.0, 'S1': 100.0, 'S2': 100.0, 'S3': 100.0, 'S4': 100.0, 'S5': 100.0})
    state = {'holdings': {'S5': 5}, 'cash': 0.0, 'updated': ''}
    plan = build_plan(scores, ref, state, 5000.0, set(), 'risk_on')
    actions = {(o['action'], o['symbol']) for o in plan['orders']}
    assert ('SELL', 'S5') in actions
    assert 'S5' not in plan['target_portfolio']
    assert 'S1' in plan['target_portfolio']
    assert 'S2' in plan['target_portfolio']


def test_hysteresis_retains_when_no_affordable_replacement() -> None:
    scores = make_scores(['S1', 'S2', 'S3', 'S4', 'S5'])
    ref = make_ref({CORE: 250.0, 'S1': 5000.0, 'S2': 5000.0, 'S3': 5000.0, 'S4': 5000.0, 'S5': 100.0})
    state = {'holdings': {'S5': 5}, 'cash': 0.0, 'updated': ''}
    plan = build_plan(scores, ref, state, 5000.0, set(), 'risk_on')
    actions = {(o['action'], o['symbol']) for o in plan['orders']}
    assert ('SELL', 'S5') not in actions
    assert 'S5' in plan['target_portfolio']


def test_corporate_action_guard_satellite() -> None:
    scores = make_scores(['S1', 'S2', 'S3'])
    ref = make_ref({CORE: 250.0, 'S1': 100.0, 'S2': 90.0, 'S3': 80.0})
    plan = build_plan(scores, ref, empty_state(), 5000.0, {'S1'}, 'risk_on')
    symbols = [o['symbol'] for o in plan['orders'] if o['action'] == 'BUY']
    assert 'S1' not in symbols
    assert 'S2' in symbols
    assert 'S3' in symbols


def test_corporate_action_guard_core() -> None:
    scores = make_scores(['S1', 'S2', 'S3'])
    ref = make_ref({CORE: 250.0, 'S1': 100.0, 'S2': 90.0, 'S3': 80.0})
    plan = build_plan(scores, ref, empty_state(), 5000.0, {CORE}, 'risk_on')
    symbols = [o['symbol'] for o in plan['orders']]
    assert CORE not in symbols
    assert CORE not in plan['target_portfolio']


def test_plan_schema() -> None:
    scores = make_scores(['S1', 'S2', 'S3', 'S4', 'S5', 'S6', 'S7'])
    ref = make_ref({CORE: 250.0, 'S1': 100.0, 'S2': 90.0, 'S3': 80.0,
                    'S4': 70.0, 'S5': 60.0, 'S6': 50.0, 'S7': 40.0})
    plan = build_plan(scores, ref, empty_state(), 5000.0, set(), 'risk_off')
    for key in ('generated', 'regime', 'capital', 'orders', 'target_portfolio', 'expected_cash', 'scores'):
        assert key in plan
    assert plan['regime'] == 'risk_off'
    assert len(plan['scores']) == 6
    for o in plan['orders']:
        for key in ('action', 'symbol', 'qty', 'ref_price', 'est_value', 'est_cost', 'reason'):
            assert key in o
        assert o['action'] in ('BUY', 'SELL')
        assert o['est_cost'] > 0
    assert json.loads(json.dumps(plan))


def test_fetch_live_cash_no_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv('KITE_API_KEY', raising=False)
    assert engine_small.fetch_live_cash() is None


def test_fetch_live_cash_stale_token(monkeypatch: pytest.MonkeyPatch, tmp_path: object) -> None:
    token = tmp_path / 'tok.json'
    token.write_text(json.dumps({'access_token': 'x', 'date': '2020-01-01', 'user_id': 'u'}))
    monkeypatch.setenv('KITE_API_KEY', 'dummy')
    monkeypatch.setattr(zerodha, 'ACCESS_TOKEN_PATH', str(token))
    assert engine_small.fetch_live_cash() is None


def simulate_execution(plan: dict, starting_cash: float) -> float:
    cash = starting_cash
    for o in plan['orders']:
        if o['action'] == 'SELL':
            cash += o['est_value'] - o['est_cost']
        else:
            cash -= o['est_value'] + o['est_cost']
        assert cash >= -1e-6, f"order {o} unexecutable: cash {cash:.2f}"
    return cash


def test_buys_funded_with_three_satellite_state() -> None:
    scores = make_scores(['S1', 'S2', 'S3', 'S4', 'S5'])
    ref = make_ref({CORE: 250.0, 'S1': 100.0, 'S2': 100.0, 'S3': 100.0, 'S4': 100.0, 'S5': 100.0})
    state = {'holdings': {'S3': 12, 'S4': 12, 'S5': 12}, 'cash': 0.0, 'updated': ''}
    plan = build_plan(scores, ref, state, 1400.0, set(), 'risk_on')
    invested = sum(q * ref[s] for s, q in plan['target_portfolio'].items())
    assert invested <= plan['capital'] + 1e-6
    assert plan['expected_cash'] >= 0
    assert len([s for s in plan['target_portfolio'] if s != CORE]) <= 2
    simulate_execution(plan, 1400.0)


def test_costs_reserved_on_clean_first_run() -> None:
    scores = make_scores(['S1', 'S2', 'S3'])
    ref = make_ref({CORE: 250.0, 'S1': 125.0, 'S2': 125.0, 'S3': 125.0})
    plan = build_plan(scores, ref, empty_state(), 5000.0, set(), 'risk_on')
    assert plan['expected_cash'] >= 0
    simulate_execution(plan, 5000.0)


def test_replacement_skipped_when_unaffordable() -> None:
    scores = make_scores(['S1', 'S2', 'S3', 'S4', 'S5'])
    ref = make_ref({CORE: 250.0, 'S1': 100.0, 'S2': 100.0, 'S3': 100.0, 'S4': 100.0, 'S5': 100.0})
    state = {'holdings': {CORE: 8, 'S3': 30, 'S5': 4}, 'cash': 0.0, 'updated': ''}
    plan = build_plan(scores, ref, state, 0.0, set(), 'risk_on')
    actions = {(o['action'], o['symbol']) for o in plan['orders']}
    assert ('SELL', 'S5') not in actions
    assert 'S5' in plan['target_portfolio']
    assert plan['expected_cash'] >= 0
    simulate_execution(plan, 0.0)


def test_unpriced_holding_raises() -> None:
    scores = make_scores(['S1', 'S2', 'S3'])
    ref = make_ref({CORE: 250.0, 'S1': 100.0, 'S2': 90.0, 'S3': 80.0})
    state = {'holdings': {'DEAD.NS': 15, 'S1': 10}, 'cash': 0.0, 'updated': ''}
    with pytest.raises(ValueError, match='DEAD.NS'):
        build_plan(scores, ref, state, 1000.0, set(), 'risk_on')


def test_flagged_core_sell_suppressed() -> None:
    scores = make_scores(['S1', 'S2', 'S3'])
    ref = make_ref({CORE: 500.0, 'S1': 100.0, 'S2': 90.0, 'S3': 80.0})
    state = {'holdings': {CORE: 10}, 'cash': 0.0, 'updated': ''}
    plan = build_plan(scores, ref, state, 2500.0, {CORE}, 'risk_on')
    assert all(o['symbol'] != CORE for o in plan['orders'])
    assert plan['target_portfolio'][CORE] == 10
    assert plan['warnings']


def test_flagged_satellite_sell_suppressed() -> None:
    scores = make_scores(['S1', 'S2', 'S3', 'S4', 'S5'])
    ref = make_ref({CORE: 250.0, 'S1': 100.0, 'S2': 100.0, 'S3': 100.0, 'S4': 100.0, 'S5': 100.0})
    state = {'holdings': {'S5': 12}, 'cash': 5000.0, 'updated': ''}
    plan = build_plan(scores, ref, state, 5000.0, {'S5'}, 'risk_on')
    assert all(o['symbol'] != 'S5' for o in plan['orders'])
    assert plan['target_portfolio']['S5'] == 12
    assert plan['warnings']


def test_sells_listed_before_buys() -> None:
    scores = make_scores(['S1', 'S2', 'S3', 'S4', 'S5'])
    ref = make_ref({CORE: 250.0, 'S1': 100.0, 'S2': 100.0, 'S3': 100.0, 'S4': 100.0, 'S5': 100.0})
    state = {'holdings': {'S5': 12}, 'cash': 0.0, 'updated': ''}
    plan = build_plan(scores, ref, state, 5000.0, set(), 'risk_on')
    actions = [o['action'] for o in plan['orders']]
    assert 'SELL' in actions and 'BUY' in actions
    assert actions.index('SELL') < actions.index('BUY')
    assert actions == sorted(actions, key=lambda a: 0 if a == 'SELL' else 1)
    simulate_execution(plan, 5000.0)


def make_price_frame(tickers: list[str], seed: int, base: float = 100.0,
                     periods: int = 300, dead: list[str] | None = None) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range(end='2026-07-17', periods=periods)
    data = {}
    for t in tickers:
        rets = rng.normal(0.0005, 0.01, periods)
        data[t] = base * np.cumprod(1 + rets)
    df = pd.DataFrame(data, index=dates)
    for t in dead or []:
        df[t] = np.nan
    df.columns = pd.MultiIndex.from_product([['Close'], tickers])
    return df


def retoday(df: pd.DataFrame) -> pd.DataFrame:
    today_ist = pd.Timestamp(engine_small.now_ist().date())
    idx = list(df.index[:-1]) + [today_ist]
    df.index = pd.DatetimeIndex(idx)
    return df


def make_adj_raw_frame(tickers: list[str], seed: int, gap_ticker: str,
                       gap_raw: bool, gap_adj: bool) -> pd.DataFrame:
    base = make_price_frame(tickers, seed=seed)
    adj = base.copy()
    raw = base.copy()
    loc = base.columns.get_loc(('Close', gap_ticker))
    if gap_adj:
        adj.iloc[-1, loc] = adj.iloc[-2, loc] * 0.5
    if gap_raw:
        raw.iloc[-1, loc] = raw.iloc[-2, loc] * 0.5
    adj.columns = pd.MultiIndex.from_product([['Adj Close'], tickers])
    raw.columns = pd.MultiIndex.from_product([['Close'], tickers])
    return pd.concat([adj, raw], axis=1)


def make_macro_frame(periods: int = 300) -> pd.DataFrame:
    rng = np.random.default_rng(7)
    dates = pd.bdate_range(end='2026-07-17', periods=periods)
    data = {
        '^INDIAVIX': 12 + rng.normal(0, 0.3, periods),
        '^NSEI': 24000 * np.cumprod(1 + rng.normal(0.0004, 0.008, periods)),
        'USDINR=X': 84 + rng.normal(0, 0.1, periods),
        'CL=F': 75 + rng.normal(0, 0.5, periods),
    }
    df = pd.DataFrame(data, index=dates)
    df.columns = pd.MultiIndex.from_product([['Close'], list(data.keys())])
    return df


@pytest.fixture
def patched_paths(monkeypatch: pytest.MonkeyPatch, tmp_path: object) -> dict[str, str]:
    paths = {
        'STATE_PATH': str(tmp_path / 'state.json'),
        'PLAN_PATH': str(tmp_path / 'plan.json'),
        'TRACK_PATH': str(tmp_path / 'track.json'),
    }
    for name, p in paths.items():
        monkeypatch.setattr(engine_small, name, p)
    monkeypatch.setattr(engine_small, 'notify', lambda *a, **k: None)
    return paths


def test_main_drops_missing_satellite_and_writes_plan(
    monkeypatch: pytest.MonkeyPatch, patched_paths: dict[str, str],
    capsys: pytest.CaptureFixture,
) -> None:

    def fake_download(tickers: list[str], **kwargs: object) -> pd.DataFrame:
        if '^INDIAVIX' in tickers:
            return make_macro_frame()
        return make_price_frame(tickers, seed=1, dead=['WIPRO.NS'])

    monkeypatch.setattr(engine_small.yf, 'download', fake_download)
    monkeypatch.setattr(sys, 'argv', ['quantshield.live.planner.py', '--capital', '5000', '--no-notify'])
    engine_small.main()
    out, err = capsys.readouterr()
    assert 'WIPRO.NS' in err
    assert 'dropping tickers' in err
    assert 'TRADE TICKET' in out
    assert os.path.exists(patched_paths['PLAN_PATH'])
    with open(patched_paths['PLAN_PATH']) as f:
        plan = json.load(f)
    for key in ('generated', 'regime', 'capital', 'orders', 'target_portfolio', 'expected_cash', 'scores'):
        assert key in plan
    assert 'WIPRO.NS' not in plan['scores']
    assert all(o['symbol'] != 'WIPRO.NS' for o in plan['orders'])
    assert plan['regime'] in ('risk_on', 'risk_off', 'crisis')


def test_main_partial_macro_failure_survives(
    monkeypatch: pytest.MonkeyPatch, patched_paths: dict[str, str],
    capsys: pytest.CaptureFixture,
) -> None:
    def fake_download(tickers: list[str], **kwargs: object) -> pd.DataFrame:
        if '^INDIAVIX' in tickers:
            df = make_macro_frame()
            df[('Close', '^INDIAVIX')] = np.nan
            return df
        return make_price_frame(tickers, seed=3)

    monkeypatch.setattr(engine_small.yf, 'download', fake_download)
    monkeypatch.setattr(sys, 'argv', ['quantshield.live.planner.py', '--capital', '5000', '--no-notify'])
    engine_small.main()
    out, err = capsys.readouterr()
    assert 'TRADE TICKET' in out
    assert '^INDIAVIX' in err
    with open(patched_paths['PLAN_PATH']) as f:
        plan = json.load(f)
    assert plan['regime'] in ('risk_on', 'risk_off', 'crisis')


def test_main_stale_holding_aborts_cleanly(
    monkeypatch: pytest.MonkeyPatch, patched_paths: dict[str, str],
    capsys: pytest.CaptureFixture,
) -> None:
    def fake_download(tickers: list[str], **kwargs: object) -> pd.DataFrame:
        if '^INDIAVIX' in tickers:
            return make_macro_frame()
        df = make_price_frame(tickers, seed=4)
        df.iloc[-10:, df.columns.get_loc(('Close', 'TCS.NS'))] = np.nan
        return df

    with open(patched_paths['STATE_PATH'], 'w') as f:
        json.dump({'holdings': {'TCS.NS': 25}, 'cash': 0.0, 'updated': ''}, f)
    monkeypatch.setattr(engine_small.yf, 'download', fake_download)
    monkeypatch.setattr(sys, 'argv', ['quantshield.live.planner.py', '--capital', '2500', '--no-notify'])
    with pytest.raises(SystemExit) as exc:
        engine_small.main()
    assert exc.value.code == 1
    _, err = capsys.readouterr()
    assert 'stale' in err
    assert 'TCS.NS' in err
    assert not os.path.exists(patched_paths['PLAN_PATH'])


def test_snapshot_inception_and_idempotency(
    monkeypatch: pytest.MonkeyPatch, patched_paths: dict[str, str],
) -> None:
    ref = make_ref({CORE: 280.0, 'S1': 100.0})
    state = {'holdings': {'S1': 20}, 'cash': 0.0, 'updated': ''}
    engine_small.write_snapshot(state, ref, 8000.0)
    engine_small.write_snapshot(state, ref, 8000.0)
    with open(patched_paths['TRACK_PATH']) as f:
        track = json.load(f)
    assert len(track['snapshots']) == 1
    snap = track['snapshots'][0]
    assert snap['portfolio_value'] == pytest.approx(10000.0)
    assert track['inception']['capital'] == pytest.approx(10000.0)
    assert snap['niftybees_benchmark_value'] == pytest.approx(10000.0)


def test_snapshot_skipped_when_holding_unpriced(
    monkeypatch: pytest.MonkeyPatch, patched_paths: dict[str, str],
    capsys: pytest.CaptureFixture,
) -> None:
    ref = make_ref({CORE: 280.0})
    state = {'holdings': {'DEAD.NS': 15}, 'cash': 1000.0, 'updated': ''}
    engine_small.write_snapshot(state, ref, 1000.0)
    _, err = capsys.readouterr()
    assert 'snapshot skipped' in err
    assert not os.path.exists(patched_paths['TRACK_PATH'])


def test_main_aborts_without_niftybees(
    monkeypatch: pytest.MonkeyPatch, patched_paths: dict[str, str],
    capsys: pytest.CaptureFixture,
) -> None:
    monkeypatch.setattr(engine_small.yf, 'download', lambda *a, **k: pd.DataFrame())
    monkeypatch.setattr(sys, 'argv', ['quantshield.live.planner.py', '--capital', '5000', '--no-notify'])
    with pytest.raises(SystemExit) as exc:
        engine_small.main()
    assert exc.value.code == 1
    _, err = capsys.readouterr()
    assert 'NIFTYBEES' in err


def test_main_corporate_action_flag(
    monkeypatch: pytest.MonkeyPatch, patched_paths: dict[str, str],
    capsys: pytest.CaptureFixture,
) -> None:

    def fake_download(tickers: list[str], **kwargs: object) -> pd.DataFrame:
        if '^INDIAVIX' in tickers:
            return make_macro_frame()
        df = make_price_frame(tickers, seed=2)
        df.iloc[-1, df.columns.get_loc(('Close', 'RELIANCE.NS'))] = (
            df.iloc[-2, df.columns.get_loc(('Close', 'RELIANCE.NS'))] * 0.5
        )
        return df

    monkeypatch.setattr(engine_small.yf, 'download', fake_download)
    monkeypatch.setattr(sys, 'argv', ['quantshield.live.planner.py', '--capital', '5000', '--no-notify'])
    engine_small.main()
    _, err = capsys.readouterr()
    assert 'RELIANCE.NS' in err
    assert 'corporate action' in err
    with open(patched_paths['PLAN_PATH']) as f:
        plan = json.load(f)
    assert all(not (o['action'] == 'BUY' and o['symbol'] == 'RELIANCE.NS') for o in plan['orders'])


def test_sector_cap_skips_breaching_candidate() -> None:
    scores = pd.Series({'AXISBANK.NS': 0.9, 'SBIN.NS': 0.6, 'S3': 0.3, 'S4': 0.1})
    ref = make_ref({CORE: 250.0, 'AXISBANK.NS': 100.0, 'SBIN.NS': 100.0, 'S3': 100.0, 'S4': 100.0})
    state = {'holdings': {CORE: 10, 'SBIN.NS': 12}, 'cash': 1300.0, 'updated': '',
             'avg_cost': {'SBIN.NS': 100.0}}
    plan = build_plan(scores, ref, state, 1300.0, set(), 'risk_on')
    actions = {(o['action'], o['symbol']) for o in plan['orders']}
    assert ('BUY', 'AXISBANK.NS') not in actions
    assert ('BUY', 'S3') in actions
    assert any('AXISBANK.NS buy skipped: financials look-through' in w for w in plan['warnings'])
    assert 'AXISBANK.NS' not in plan['target_portfolio']
    simulate_execution(plan, 1300.0)


def test_existing_breach_warns_never_sells() -> None:
    scores = pd.Series({'SBIN.NS': 0.9, 'S3': 0.5, 'S4': 0.1})
    ref = make_ref({CORE: 250.0, 'SBIN.NS': 100.0, 'S3': 100.0, 'S4': 100.0})
    state = {'holdings': {CORE: 10, 'SBIN.NS': 30}, 'cash': 0.0, 'updated': '',
             'avg_cost': {'SBIN.NS': 100.0}}
    plan = build_plan(scores, ref, state, 0.0, set(), 'risk_on')
    assert plan['orders'] == []
    assert any('exceeds cap' in w for w in plan['warnings'])
    assert plan['target_portfolio']['SBIN.NS'] == 30
    assert plan['target_portfolio'][CORE] == 10


def test_replacement_blocked_below_score_margin() -> None:
    scores = pd.Series({'S1': 0.9, 'S2': 0.30, 'S3': 0.25, 'S4': 0.22, 'S5': 0.20})
    ref = make_ref({CORE: 250.0, 'S1': 100.0, 'S2': 100.0, 'S3': 100.0, 'S4': 100.0, 'S5': 100.0})
    state = {'holdings': {'S5': 5}, 'cash': 0.0, 'updated': '', 'avg_cost': {'S5': 100.0}}
    plan = build_plan(scores, ref, state, 5000.0, set(), 'risk_on')
    actions = {(o['action'], o['symbol']) for o in plan['orders']}
    assert ('SELL', 'S5') not in actions
    assert ('BUY', 'S2') not in actions
    assert plan['target_portfolio']['S5'] == 5
    simulate_execution(plan, 5000.0)


def test_replacement_executes_above_score_margin() -> None:
    scores = pd.Series({'S1': 0.9, 'S2': 0.40, 'S3': 0.25, 'S4': 0.22, 'S5': 0.20})
    ref = make_ref({CORE: 250.0, 'S1': 100.0, 'S2': 100.0, 'S3': 100.0, 'S4': 100.0, 'S5': 100.0})
    state = {'holdings': {'S5': 5}, 'cash': 0.0, 'updated': '', 'avg_cost': {'S5': 100.0}}
    plan = build_plan(scores, ref, state, 5000.0, set(), 'risk_on')
    sells = {o['symbol']: o for o in plan['orders'] if o['action'] == 'SELL'}
    buys = {o['symbol']: o for o in plan['orders'] if o['action'] == 'BUY'}
    assert 'S5' in sells and 'replaced by S2' in sells['S5']['reason']
    assert 'S2' in buys and 'replacement entry' in buys['S2']['reason']
    assert 'S5' not in plan['target_portfolio']
    simulate_execution(plan, 5000.0)


def test_replacement_falls_through_to_next_affordable() -> None:
    scores = make_scores(['S1', 'S2', 'S3', 'S4', 'S5'])
    ref = make_ref({CORE: 250.0, 'S1': 100.0, 'S2': 700.0, 'S3': 100.0, 'S4': 100.0, 'S5': 100.0})
    state = {'holdings': {CORE: 11, 'S5': 5}, 'cash': 2250.0, 'updated': '', 'avg_cost': {'S5': 100.0}}
    plan = build_plan(scores, ref, state, 2250.0, set(), 'risk_on')
    sells = {o['symbol']: o for o in plan['orders'] if o['action'] == 'SELL'}
    buys = {o['symbol']: o for o in plan['orders'] if o['action'] == 'BUY'}
    assert 'S2' not in buys
    assert 'S5' in sells and 'replaced by S3' in sells['S5']['reason']
    assert 'S3' in buys and 'replacement entry' in buys['S3']['reason']
    simulate_execution(plan, 2250.0)


def wide_setup() -> tuple[pd.Series, pd.Series]:
    syms = [f'S{i}' for i in range(1, 15)]
    scores = make_scores(syms)
    prices = {CORE: 250.0, 'S14': 100.0}
    for s in syms[:-1]:
        prices[s] = 5000.0
    return scores, make_ref(prices)


def test_below_rank_streak_increment_and_persistence_old_schema() -> None:
    scores, ref = wide_setup()
    state = {'holdings': {'S14': 5}, 'cash': 0.0, 'updated': ''}
    plan1 = build_plan(scores, ref, state, 1000.0, set(), 'risk_on')
    assert state['below_rank_streak']['S14'] == 1
    assert all(o['symbol'] != 'S14' for o in plan1['orders'])
    assert any('missing avg_cost' in w for w in plan1['warnings'])
    state['streak_updated'] = '2000-01-01'
    plan2 = build_plan(scores, ref, state, 1000.0, set(), 'risk_on')
    assert state['below_rank_streak']['S14'] == 2
    assert all(o['symbol'] != 'S14' for o in plan2['orders'])
    state['streak_updated'] = '2000-01-02'
    plan3 = build_plan(scores, ref, state, 1000.0, set(), 'risk_on')
    assert state['below_rank_streak']['S14'] == 3
    sells = {o['symbol']: o for o in plan3['orders'] if o['action'] == 'SELL'}
    assert 'S14' in sells
    assert sells['S14']['reason'] == 'persistent signal deterioration'
    assert 'S14' not in plan3['target_portfolio']


def test_below_rank_streak_increments_once_per_day() -> None:
    scores, ref = wide_setup()
    state = {'holdings': {'S14': 5}, 'cash': 0.0, 'updated': ''}
    plan = None
    for _ in range(4):
        plan = build_plan(scores, ref, state, 1000.0, set(), 'risk_on')
    assert state['below_rank_streak']['S14'] == 1
    assert all(o['symbol'] != 'S14' for o in plan['orders'])
    assert 'S14' in plan['target_portfolio']


def test_below_rank_streak_resets_on_recovery() -> None:
    scores, ref = wide_setup()
    state = {'holdings': {'S14': 5}, 'cash': 0.0, 'updated': '',
             'below_rank_streak': {'S14': 2}, 'avg_cost': {'S14': 100.0}}
    recovered = scores.copy()
    recovered['S14'] = 1.5
    recovered = recovered.sort_values(ascending=False)
    plan = build_plan(recovered, ref, state, 1000.0, set(), 'risk_on')
    assert state['below_rank_streak']['S14'] == 0
    assert all(o['symbol'] != 'S14' for o in plan['orders'])
    assert plan['target_portfolio']['S14'] == 5


def test_loss_stop_sell_proposal() -> None:
    scores = make_scores(['S1', 'S2', 'S3', 'S4', 'S5'])
    ref = make_ref({CORE: 250.0, 'S1': 100.0, 'S2': 100.0, 'S3': 100.0, 'S4': 100.0, 'S5': 100.0})
    state = {'holdings': {'S1': 5}, 'cash': 0.0, 'updated': '', 'avg_cost': {'S1': 130.0}}
    plan = build_plan(scores, ref, state, 5000.0, set(), 'risk_on')
    sells = {o['symbol']: o for o in plan['orders'] if o['action'] == 'SELL'}
    assert 'S1' in sells
    assert sells['S1']['reason'] == 'position stop -20%'
    assert 'S1' not in plan['target_portfolio']
    simulate_execution(plan, 5000.0)


def test_loss_within_stop_not_sold() -> None:
    scores = make_scores(['S1', 'S2', 'S3', 'S4', 'S5'])
    ref = make_ref({CORE: 250.0, 'S1': 100.0, 'S2': 100.0, 'S3': 100.0, 'S4': 100.0, 'S5': 100.0})
    state = {'holdings': {'S1': 5}, 'cash': 0.0, 'updated': '', 'avg_cost': {'S1': 120.0}}
    plan = build_plan(scores, ref, state, 5000.0, set(), 'risk_on')
    assert all(not (o['action'] == 'SELL' and o['symbol'] == 'S1') for o in plan['orders'])
    assert 'S1' in plan['target_portfolio']


def test_no_buy_blocks_buys_but_allows_stop_sell() -> None:
    scores = make_scores(['S1', 'S2', 'S3', 'S4', 'S5'])
    ref = make_ref({CORE: 250.0, 'S1': 100.0, 'S2': 100.0, 'S3': 100.0, 'S4': 100.0, 'S5': 100.0})
    state = {'holdings': {'S1': 5}, 'cash': 0.0, 'updated': '', 'avg_cost': {'S1': 130.0}}
    plan = build_plan(scores, ref, state, 5000.0, set(), 'risk_on', no_buy=frozenset({'S1', 'S2'}))
    sells = {o['symbol']: o for o in plan['orders'] if o['action'] == 'SELL'}
    buys = {o['symbol']: o for o in plan['orders'] if o['action'] == 'BUY'}
    assert 'S1' in sells
    assert sells['S1']['reason'] == 'position stop -20%'
    assert 'S1' not in buys
    assert 'S2' not in buys
    assert 'S3' in buys
    simulate_execution(plan, 5000.0)


def test_missing_avg_cost_tolerated_with_warning() -> None:
    scores = make_scores(['S1', 'S2', 'S3', 'S4', 'S5'])
    ref = make_ref({CORE: 250.0, 'S1': 100.0, 'S2': 100.0, 'S3': 100.0, 'S4': 100.0, 'S5': 100.0})
    state = {'holdings': {'S1': 5}, 'cash': 0.0, 'updated': '', 'avg_cost': {}}
    plan = build_plan(scores, ref, state, 5000.0, set(), 'risk_on')
    assert any('S1 missing avg_cost' in w for w in plan['warnings'])
    assert all(not (o['action'] == 'SELL' and o['symbol'] == 'S1') for o in plan['orders'])
    assert 'S1' in plan['target_portfolio']


def test_snapshot_fallback_when_live_cash_unavailable(
    monkeypatch: pytest.MonkeyPatch, patched_paths: dict[str, str],
    capsys: pytest.CaptureFixture,
) -> None:
    def fake_download(tickers: list[str], **kwargs: object) -> pd.DataFrame:
        if '^INDIAVIX' in tickers:
            return make_macro_frame()
        return retoday(make_price_frame(tickers, seed=5))

    with open(patched_paths['STATE_PATH'], 'w') as f:
        json.dump({'holdings': {CORE: 9}, 'cash': 416.35, 'updated': ''}, f)
    monkeypatch.setattr(engine_small.yf, 'download', fake_download)
    monkeypatch.setattr(engine_small, 'fetch_live_cash', lambda: None)
    monkeypatch.setattr(sys, 'argv', ['quantshield.live.planner.py', '--snapshot'])
    engine_small.main()
    _, err = capsys.readouterr()
    assert 'snapshot-only fallback' in err
    assert not os.path.exists(patched_paths['PLAN_PATH'])
    with open(patched_paths['TRACK_PATH']) as f:
        track = json.load(f)
    snap = track['snapshots'][-1]
    assert snap['cash'] == pytest.approx(416.35)
    assert snap['portfolio_value'] > 416.35


def test_snapshot_mode_never_plans_even_with_live_cash(
    monkeypatch: pytest.MonkeyPatch, patched_paths: dict[str, str],
) -> None:
    def fake_download(tickers: list[str], **kwargs: object) -> pd.DataFrame:
        if '^INDIAVIX' in tickers:
            return make_macro_frame()
        return retoday(make_price_frame(tickers, seed=6))

    original_state = {'holdings': {CORE: 9}, 'cash': 416.35, 'updated': ''}
    with open(patched_paths['STATE_PATH'], 'w') as f:
        json.dump(original_state, f)
    notified: list[str] = []
    monkeypatch.setattr(engine_small, 'notify', lambda *a, **k: notified.append(a))
    monkeypatch.setattr(engine_small.yf, 'download', fake_download)
    monkeypatch.setattr(engine_small, 'fetch_live_cash', lambda: 5000.0)
    monkeypatch.setattr(sys, 'argv', ['quantshield.live.planner.py', '--snapshot'])
    engine_small.main()
    assert not os.path.exists(patched_paths['PLAN_PATH'])
    assert notified == []
    with open(patched_paths['STATE_PATH']) as f:
        assert json.load(f) == original_state
    with open(patched_paths['TRACK_PATH']) as f:
        track = json.load(f)
    assert track['snapshots'][-1]['cash'] == pytest.approx(5000.0)


def test_snapshot_skipped_when_prices_stale(
    patched_paths: dict[str, str], capsys: pytest.CaptureFixture,
) -> None:
    ref = pd.Series({CORE: 280.0}, name=pd.Timestamp('2026-01-02'))
    state = {'holdings': {}, 'cash': 100.0, 'updated': ''}
    engine_small.write_snapshot(state, ref, 100.0)
    _, err = capsys.readouterr()
    assert 'snapshot skipped' in err
    assert not os.path.exists(patched_paths['TRACK_PATH'])


def test_main_split_suppresses_exit_and_warns(
    monkeypatch: pytest.MonkeyPatch, patched_paths: dict[str, str],
    capsys: pytest.CaptureFixture,
) -> None:
    def fake_download(tickers: list[str], **kwargs: object) -> pd.DataFrame:
        if '^INDIAVIX' in tickers:
            return make_macro_frame()
        return make_adj_raw_frame(tickers, seed=7, gap_ticker='RELIANCE.NS',
                                  gap_raw=True, gap_adj=False)

    with open(patched_paths['STATE_PATH'], 'w') as f:
        json.dump({'holdings': {'RELIANCE.NS': 1}, 'cash': 0.0, 'updated': '',
                   'avg_cost': {'RELIANCE.NS': 100000.0}}, f)
    monkeypatch.setattr(engine_small.yf, 'download', fake_download)
    monkeypatch.setattr(sys, 'argv', ['quantshield.live.planner.py', '--capital', '5000', '--no-notify'])
    engine_small.main()
    _, err = capsys.readouterr()
    assert 'split/bonus suspected' in err
    assert 'verify avg_cost' in err
    with open(patched_paths['PLAN_PATH']) as f:
        plan = json.load(f)
    assert all(o['symbol'] != 'RELIANCE.NS' for o in plan['orders'])
    assert plan['target_portfolio'].get('RELIANCE.NS') == 1
    assert any('suppressed' in w for w in plan['warnings'])


def test_main_crash_stop_still_fires(
    monkeypatch: pytest.MonkeyPatch, patched_paths: dict[str, str],
    capsys: pytest.CaptureFixture,
) -> None:
    def fake_download(tickers: list[str], **kwargs: object) -> pd.DataFrame:
        if '^INDIAVIX' in tickers:
            return make_macro_frame()
        return make_adj_raw_frame(tickers, seed=8, gap_ticker='RELIANCE.NS',
                                  gap_raw=True, gap_adj=True)

    with open(patched_paths['STATE_PATH'], 'w') as f:
        json.dump({'holdings': {'RELIANCE.NS': 1}, 'cash': 0.0, 'updated': '',
                   'avg_cost': {'RELIANCE.NS': 100000.0}}, f)
    monkeypatch.setattr(engine_small.yf, 'download', fake_download)
    monkeypatch.setattr(sys, 'argv', ['quantshield.live.planner.py', '--capital', '5000', '--no-notify'])
    engine_small.main()
    _, err = capsys.readouterr()
    assert 'corporate action or shock' in err
    with open(patched_paths['PLAN_PATH']) as f:
        plan = json.load(f)
    sells = {o['symbol']: o for o in plan['orders'] if o['action'] == 'SELL'}
    assert 'RELIANCE.NS' in sells
    assert sells['RELIANCE.NS']['reason'] == 'position stop -20%'
    assert all(not (o['action'] == 'BUY' and o['symbol'] == 'RELIANCE.NS') for o in plan['orders'])


def test_plan_run_still_requires_capital(
    monkeypatch: pytest.MonkeyPatch, patched_paths: dict[str, str],
    capsys: pytest.CaptureFixture,
) -> None:
    monkeypatch.setattr(engine_small, 'fetch_live_cash', lambda: None)
    monkeypatch.setattr(sys, 'argv', ['quantshield.live.planner.py', '--no-notify'])
    with pytest.raises(SystemExit) as exc:
        engine_small.main()
    assert exc.value.code == 1
    _, err = capsys.readouterr()
    assert 'pass --capital' in err


class TestEtfCostModel:
    def test_etf_buy_has_no_stt(self) -> None:
        stock = trade_cost('BUY', 2481.75)
        etf = trade_cost('BUY', 2481.75, etf=True)
        assert stock - etf == pytest.approx(0.001 * 2481.75, abs=0.01)

    def test_etf_sell_stt_reduced(self) -> None:
        stock = trade_cost('SELL', 2481.75)
        etf = trade_cost('SELL', 2481.75, etf=True)
        assert stock - etf == pytest.approx(0.001 * 2481.75 - 0.00001 * 2481.75, abs=0.01)

    def test_contract_note_calibration_2026_07_20(self) -> None:
        total = trade_cost('BUY', 1054.80) + trade_cost('BUY', 1047.10) + trade_cost('BUY', 2481.75, etf=True)
        assert total == pytest.approx(3.18, abs=0.75)


GOLDEN_PATH = os.path.join(os.path.dirname(__file__), 'fixtures', 'plan_golden.json')


def golden_inputs() -> tuple[pd.Series, pd.Series, dict, float, set[str], frozenset[str], str]:
    tickers = [CORE] + list(INDIA_TICKERS)
    rng = np.random.default_rng(3)
    dates = pd.bdate_range(end='2026-07-17', periods=300)
    bases = rng.uniform(80.0, 3000.0, len(tickers))
    rets = rng.normal(0.0005, 0.012, (len(dates), len(tickers)))
    close = pd.DataFrame(bases * np.cumprod(1 + rets, axis=0), index=dates, columns=tickers)
    macro = pd.DataFrame({
        '^INDIAVIX': 13 + rng.normal(0, 0.4, len(dates)),
        '^NSEI': 24000 * np.cumprod(1 + rng.normal(0.0004, 0.008, len(dates))),
        'USDINR=X': 84 + rng.normal(0, 0.1, len(dates)),
        'CL=F': 75 + rng.normal(0, 0.5, len(dates)),
    }, index=dates)
    scores = engine_small.compute_scores(close[list(INDIA_TICKERS)], macro, 'risk_on')
    ref = close.iloc[-1]
    held = {'TCS.NS': 1.0, 'SBIN.NS': 1.4, 'ITC.NS': 0.9}
    holdings = {s: max(1, int(1000 // float(ref[s]))) for s in held}
    avg_cost = {s: round(float(ref[s]) * k, 2) for s, k in held.items()}
    state = {'holdings': holdings, 'cash': 0.0, 'updated': '', 'avg_cost': avg_cost,
             'below_rank_streak': {'ITC.NS': 2}, 'streak_updated': '2026-07-16'}
    return scores, ref, state, 5000.0, {'HINDUNILVR.NS'}, frozenset({'MARUTI.NS'}), 'risk_on'


def golden_result() -> dict:
    scores, ref, state, cash, flagged, no_buy, regime = golden_inputs()
    plan = build_plan(scores, ref, state, cash, flagged, regime, no_buy=no_buy)
    plan.pop('generated')
    return {
        'scores': {s: round(float(v), 10) for s, v in scores.items()},
        'plan': json.loads(json.dumps(plan)),
        'below_rank_streak': state['below_rank_streak'],
    }


def test_plan_golden_regression() -> None:
    with open(GOLDEN_PATH) as f:
        golden = json.load(f)
    got = golden_result()
    assert got['scores'] == golden['scores']
    assert got['plan'] == golden['plan']
    assert got['below_rank_streak'] == golden['below_rank_streak']


if __name__ == '__main__':
    with open(GOLDEN_PATH, 'w') as f:
        json.dump(golden_result(), f, indent=2)
    print(GOLDEN_PATH)
