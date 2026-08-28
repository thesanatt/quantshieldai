import json
import re
from pathlib import Path

import pytest

from quantshield.config import DSR_TRIALS, MARKETS
from tests.conftest import REPO_ROOT, walk_keys

DATA_DIR = REPO_ROOT / 'dashboard' / 'src' / 'data'
TOP_KEYS = {
    'market', 'generated', 'currency', 'benchmark', 'universe', 'regime', 'weights',
    'walk_forward', 'deflated_sharpe', 'in_sample', 'cvar', 'correlation', 'risk_limits',
}
WALK_FORWARD_KEYS = {
    'min_train_days', 'step_days', 'start', 'end', 'total_periods', 'win_periods', 'win_rate',
    'fallback_periods', 'cost_model', 'port_return', 'bench_return', 'alpha', 'port_sharpe', 'bench_sharpe',
    'port_vol', 'bench_vol', 'port_maxdd', 'bench_maxdd', 'alpha_t_stat', 'alpha_p_value',
    'alpha_significant', 'bootstrap_ci', 'periods', 'equity_curve', 'regime_performance',
}
DSR_KEYS = {
    'observed_sharpe_annual', 'benchmark_sharpe_annual', 'expected_max_sharpe_annual', 'sr_star_annual', 'psr',
    'p_value', 'is_significant', 'n_trials', 't_obs', 'skewness', 'excess_kurtosis', 'periods_per_year',
}
WEIGHT_KEYS = {'ticker', 'weight_pct', 'price', 'momentum', 'vol_adj_momentum', 'mean_reversion', 'trend',
               'cross_asset', 'composite', 'beta'}
FORBIDDEN_TEXT = ('\u2014', '\u2013', 'voo_', 'cash', 'avg_cost', 'access_token', 'api_key', 'user_id')


@pytest.fixture(scope='module', params=['us', 'india'])
def market(request: pytest.FixtureRequest) -> str:
    return request.param


@pytest.fixture(scope='module')
def payload(market: str) -> dict:
    return json.loads((DATA_DIR / f'{market}.json').read_text())


def test_files_exist() -> None:
    for name in ('us.json', 'india.json', 'orb.json', 'ledger.json'):
        assert (DATA_DIR / name).is_file(), name


def test_top_level_contract(payload: dict, market: str) -> None:
    cfg = MARKETS[market]
    assert set(payload) >= TOP_KEYS
    assert set(payload) - TOP_KEYS <= {'fama_french'}
    assert payload['market'] == market
    assert payload['currency'] == cfg.currency
    assert payload['benchmark'] == {'ticker': cfg.benchmark, 'label': cfg.benchmark_label}
    assert re.fullmatch(r'\d{4}-\d{2}-\d{2}', payload['generated'])
    assert sorted(payload['universe']) == sorted(cfg.tickers)
    assert set(payload['in_sample']) == {'port_return', 'bench_return', 'alpha', 'port_sharpe', 'bench_sharpe',
                                         'port_maxdd', 'bench_maxdd'}
    assert set(payload['cvar']) == {'portfolio_cvar', 'var', 'confidence'}
    assert payload['cvar']['portfolio_cvar'] <= payload['cvar']['var'] < 0
    assert set(payload['correlation']) == {'avg_30d', 'warning', 'top_pairs'}
    assert type(payload['correlation']['warning']) is bool
    assert payload['correlation']['warning'] is (payload['correlation']['avg_30d'] > 0.6)
    assert payload['risk_limits'] == {
        'min_weight': cfg.min_weight, 'max_weight': cfg.max_weight, 'max_single_stock': cfg.max_single_stock,
        'max_sector': cfg.max_sector_pct, 'max_portfolio_beta': cfg.max_portfolio_beta,
        'max_monthly_cvar': cfg.max_monthly_cvar,
    }


def test_no_private_or_legacy_keys_anywhere(payload: dict) -> None:
    keys = set(walk_keys(payload))
    assert not {k for k in keys if k.startswith('voo_')}
    assert {k for k in keys if k.startswith('bench_')} >= {'bench_return', 'bench_sharpe', 'bench_maxdd', 'bench_vol'}
    assert not keys & {'cash', 'avg_cost', 'holdings', 'order_id', 'user_id', 'client_id', 'api_key', 'access_token'}
    text = (DATA_DIR / f"{payload['market']}.json").read_text()
    for needle in FORBIDDEN_TEXT:
        assert needle not in text, needle
    assert text.isascii()


def test_regime_block(payload: dict, market: str) -> None:
    regime = payload['regime']
    assert set(regime) == {'detected', 'confidence', 'vix', 'signal_weights'}
    assert regime['detected'] in ('risk_on', 'risk_off', 'crisis')
    assert 0.0 <= regime['confidence'] <= 1.0
    assert regime['vix'] > 0
    assert regime['signal_weights'] == MARKETS[market].regime_weights[regime['detected']]


def test_weights_sum_to_100_and_respect_limits(payload: dict, market: str) -> None:
    cfg = MARKETS[market]
    rows = payload['weights']
    assert len(rows) == len(cfg.tickers)
    assert all(set(r) == WEIGHT_KEYS for r in rows)
    assert [r['ticker'] for r in rows] == sorted(payload['universe'], key=lambda t: -next(r['weight_pct'] for r in rows if r['ticker'] == t))
    assert sum(r['weight_pct'] for r in rows) == pytest.approx(100.0, abs=0.011)
    cap = min(cfg.max_weight, cfg.max_single_stock) * 100
    for r in rows:
        assert cfg.min_weight * 100 - 0.01 <= r['weight_pct'] <= cap + 0.01, r
        assert r['price'] > 0
        assert -1.0 <= r['composite'] <= 1.0
    by_ticker = {r['ticker']: r['weight_pct'] for r in rows}
    for sector, members in cfg.sector_map.items():
        assert sum(by_ticker[t] for t in members) <= cfg.max_sector_pct * 100 + 0.02, sector


def test_walk_forward_block_is_internally_consistent(payload: dict, market: str) -> None:
    wf = payload['walk_forward']
    assert set(wf) == WALK_FORWARD_KEYS
    assert wf['min_train_days'] == 252 and wf['step_days'] == 21
    assert wf['fallback_periods'] == 0
    assert wf['total_periods'] == len(wf['periods']) >= 60
    assert wf['win_periods'] == sum(1 for p in wf['periods'] if p['alpha'] > 0)
    assert wf['win_rate'] == pytest.approx(wf['win_periods'] / wf['total_periods'] * 100, abs=0.06)
    assert wf['alpha'] == pytest.approx(wf['port_return'] - wf['bench_return'], abs=0.011)
    assert wf['port_maxdd'] < 0 and wf['bench_maxdd'] < 0
    assert 0 <= wf['alpha_p_value'] <= 1
    assert type(wf['alpha_significant']) is bool
    assert wf['alpha_significant'] is (wf['alpha_p_value'] < 0.05)
    assert wf['start'] == wf['periods'][0]['period_start']
    assert wf['end'] == wf['periods'][-1]['period_end']
    for prev, nxt in zip(wf['periods'], wf['periods'][1:], strict=False):
        assert prev['period_end'] < nxt['period_start']
    for p in wf['periods']:
        assert set(p) == {'period_start', 'period_end', 'port_return', 'bench_return', 'alpha', 'regime'}
        assert p['regime'] in ('risk_on', 'risk_off', 'crisis')
    ci = wf['bootstrap_ci']
    assert set(ci) == {'sharpe_ci', 'alpha_ci', 'alpha_includes_zero', 'n_bootstrap', 'ci_level'}
    assert ci['n_bootstrap'] == 10000 and ci['ci_level'] == 0.95
    assert ci['alpha_includes_zero'] is (ci['alpha_ci'][0] <= 0 <= ci['alpha_ci'][1])
    assert set(wf['regime_performance']) == {p['regime'] for p in wf['periods']}
    assert sum(v['n_months'] for v in wf['regime_performance'].values()) == wf['total_periods']
    expected_cost = 'flat 10 bps per unit of one-way turnover' if market == 'us' else 'NSE CNC delivery schedule'
    assert wf['cost_model'].startswith(expected_cost)


def test_equity_curve_starts_at_100_and_ends_at_reported_return(payload: dict) -> None:
    wf = payload['walk_forward']
    curve = wf['equity_curve']
    assert curve[0]['portfolio'] == 100.0 and curve[0]['benchmark'] == 100.0
    assert 2 <= len(curve) <= 400
    dates = [p['date'] for p in curve]
    assert dates == sorted(dates) and len(set(dates)) == len(dates)
    assert curve[0]['date'] < wf['start']
    assert curve[-1]['date'] == wf['end']
    assert curve[-1]['portfolio'] == pytest.approx(100.0 * (1 + wf['port_return'] / 100), abs=0.02)
    assert curve[-1]['benchmark'] == pytest.approx(100.0 * (1 + wf['bench_return'] / 100), abs=0.02)


def test_deflated_sharpe_block(payload: dict) -> None:
    dsr = payload['deflated_sharpe']
    wf = payload['walk_forward']
    assert set(dsr) == DSR_KEYS
    assert dsr['n_trials'] == DSR_TRIALS == 37
    assert dsr['periods_per_year'] == 252
    assert dsr['t_obs'] == wf['total_periods'] * 21
    assert dsr['observed_sharpe_annual'] == wf['port_sharpe']
    assert dsr['benchmark_sharpe_annual'] == wf['bench_sharpe']
    assert 0.0 <= dsr['p_value'] <= 1.0
    assert dsr['psr'] == pytest.approx(1.0 - dsr['p_value'], abs=1e-6)
    assert type(dsr['is_significant']) is bool
    assert dsr['is_significant'] is (dsr['p_value'] < 0.05)
    assert dsr['sr_star_annual'] >= dsr['expected_max_sharpe_annual'] > 0


def test_fama_french_only_on_us_with_real_factors() -> None:
    us = json.loads((DATA_DIR / 'us.json').read_text())
    india = json.loads((DATA_DIR / 'india.json').read_text())
    assert 'fama_french' not in india
    ff = us['fama_french']
    assert not ff.get('is_synthetic')
    assert 'error' not in ff
    assert ff['factors_used'] == ['Mkt-RF', 'SMB', 'HML', 'RMW', 'CMA', 'Mom']
    assert set(ff['factor_betas']) == set(ff['factors_used'])
    assert ff['n_months'] >= 12
    assert 0.0 <= ff['r_squared'] <= 1.0
    assert ff['residual_alpha_annualized'] == pytest.approx(ff['alpha'] * 12, abs=1e-3)


def test_live_export_shape_when_present() -> None:
    path = REPO_ROOT / 'dashboard' / 'public' / 'live' / 'dashboard.json'
    if not path.exists():
        pytest.skip('live export is generated locally by quantshield.live.export and is not committed')
    live = json.loads(path.read_text())
    assert set(live) == {'generated', 'quotes_live', 'account', 'metrics', 'series', 'execution', 'plan', 'monitor'}
    keys = set(walk_keys(live))
    assert not keys & {'cash', 'avg_cost', 'holdings', 'capital', 'order_id', 'units', 'portfolio_value'}
    assert live['series']['equity_curve'][0]['portfolio'] == 100.0
    assert live['monitor']['loop_status'] in ('active', 'idle', 'halted')


def test_orb_card_shape() -> None:
    orb = json.loads((DATA_DIR / 'orb.json').read_text())
    assert orb['sessions'] >= orb['triggered'] >= orb['wins'] >= 0
    assert orb['net'] == pytest.approx(orb['gross'] - orb['costs'], abs=0.011)
    assert orb['win_rate_pct'] == pytest.approx(orb['wins'] / orb['triggered'] * 100, abs=0.06)
    assert 0.0 <= orb['bootstrap_p'] <= 1.0


def test_ledger_entries_have_verdicts_and_sources() -> None:
    ledger = json.loads((DATA_DIR / 'ledger.json').read_text())
    assert len(ledger) == DSR_TRIALS
    assert len({entry['name'] for entry in ledger}) == len(ledger)
    for entry in ledger:
        assert set(entry) == {'name', 'market', 'category', 'hypothesis', 'key_statistic', 'verdict', 'note', 'source'}
        assert entry['market'] in ('us', 'india', 'both')
        assert entry['verdict'] in ('approved', 'conditional', 'rejected')
        for source in entry['source'].split(';'):
            assert (REPO_ROOT / source.strip()).exists(), source


def test_data_dir_is_the_repo_not_the_test_root(repo_root: Path) -> None:
    assert DATA_DIR == repo_root / 'dashboard' / 'src' / 'data'
