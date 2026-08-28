import argparse
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta

import pandas as pd
import yfinance as yf
from dotenv import load_dotenv

from quantshield.broker.zerodha import get_kite
from quantshield.config import INDIA_MACRO_TICKERS, INDIA_REGIME_WEIGHTS, INDIA_SECTOR_MAP, INDIA_TICKERS
from quantshield.costs import delivery_cost
from quantshield.live.notify import notify
from quantshield.paths import PORTFOLIO
from quantshield.signals.cross_asset import india_cross_asset_signals
from quantshield.signals.mean_reversion import rsi_signal
from quantshield.signals.momentum import momentum_signal, vol_adj_momentum
from quantshield.signals.regime import india_detect_regime
from quantshield.signals.trend import trend_signal
from quantshield.utils import atomic_write_json, load_json, log, now_ist, rank_normalize, sanitize

CORE = 'NIFTYBEES.NS'
MIN_TRADE_VALUE = 800.0
STALE_SESSIONS = 5
KEEP_RANK = 4
SWAP_SCORE_MARGIN = 0.15
FLOOR_RANK = 12
FLOOR_STREAK = 3
LOSS_STOP = 0.20
CORP_ACTION_SESSIONS = 5
SATELLITE_SLOTS = 2
CORE_TARGET_FRACTION = 0.5
FINANCIAL_SECTORS = frozenset({'banks', 'finance'})
CORE_FINANCIALS_WEIGHT = 0.35
MAX_FINANCIALS_LOOKTHROUGH = 0.50
FINANCIAL_TICKERS = frozenset(t for sector in FINANCIAL_SECTORS for t in INDIA_SECTOR_MAP.get(sector, []))

STATE_PATH = str(PORTFOLIO / 'small_account_state.json')
PLAN_PATH = str(PORTFOLIO / 'small_account_plan.json')
TRACK_PATH = str(PORTFOLIO / 'small_track_record.json')


def fetch_live_cash() -> float | None:
    kite = get_kite()
    if kite is None:
        log("WARNING: KITE_API_KEY missing or access token not dated today; cannot fetch live cash")
        return None
    try:
        margins = kite.margins(segment='equity')
        return float(margins['available']['live_balance'])
    except Exception as exc:
        log(f"WARNING: live cash fetch failed: {exc}")
        return None


def download_close(tickers: list[str], days: int = 550) -> tuple[pd.DataFrame, pd.DataFrame]:
    end = datetime.now()
    start = end - timedelta(days=days)
    data = yf.download(tickers, start=start, end=end, auto_adjust=False, progress=False)
    if data.empty:
        return pd.DataFrame(), pd.DataFrame()
    if isinstance(data.columns, pd.MultiIndex):
        fields = data.columns.get_level_values(0)
        raw = data['Close']
        adj = data['Adj Close'] if 'Adj Close' in fields else raw
    else:
        raw = data
        adj = data
    if isinstance(adj, pd.Series):
        adj = adj.to_frame(tickers[0])
    if isinstance(raw, pd.Series):
        raw = raw.to_frame(tickers[0])
    return adj, raw


def load_state() -> dict:
    if os.path.exists(STATE_PATH):
        state = load_json(STATE_PATH)
        if state is None:
            log(f"ERROR: state file unreadable: {STATE_PATH}")
            sys.exit(1)
        return state
    state = {'holdings': {}, 'cash': 0.0, 'updated': now_ist().isoformat()}
    atomic_write_json(STATE_PATH, state)
    return state


def buy_qty_affordable(px: float, cash: float, desired: int, etf: bool = False) -> int:
    qty = desired
    while qty > 0 and qty * px + delivery_cost('BUY', qty * px, etf) > cash:
        qty -= 1
    return qty


def fin_exposure(sym: str, qty: int, px: float) -> float:
    if sym == CORE:
        return qty * px * CORE_FINANCIALS_WEIGHT
    if sym in FINANCIAL_TICKERS:
        return qty * px
    return 0.0


def compute_scores(sat_close: pd.DataFrame, macro_close: pd.DataFrame, regime: str) -> pd.Series:
    if len(sat_close) < 273:
        log(f"WARNING: only {len(sat_close)} trading days; momentum lookback may be degraded")
    returns = sat_close.pct_change().dropna()
    benchmark_returns = macro_close['^NSEI'].pct_change().dropna() if '^NSEI' in macro_close.columns else None
    weights = INDIA_REGIME_WEIGHTS[regime]
    mom = rank_normalize(momentum_signal(sat_close))
    vmom = rank_normalize(vol_adj_momentum(returns))
    rsi = rank_normalize(rsi_signal(sat_close))
    trend = rank_normalize(trend_signal(sat_close))
    cross_raw, _ = india_cross_asset_signals(
        sat_close, macro_close, returns,
        benchmark_returns=benchmark_returns, sector_map=INDIA_SECTOR_MAP,
    )
    cross = rank_normalize(cross_raw)
    composite = (
        weights['momentum'] * mom +
        weights['vol_adj_momentum'] * vmom +
        weights['mean_reversion'] * rsi +
        weights['trend'] * trend +
        weights['cross_asset'] * cross
    )
    return composite.sort_values(ascending=False)


@dataclass
class Plan:
    scores: pd.Series
    ref: pd.Series
    holdings: dict[str, int]
    total_capital: float
    cash: float
    flagged: set[str]
    no_buy: frozenset[str]
    ranks: dict[str, int] = field(default_factory=dict)
    fin_value: float = 0.0
    warnings: list[str] = field(default_factory=list)
    sells: list[tuple[str, int, str]] = field(default_factory=list)
    buys: list[tuple[str, int, str]] = field(default_factory=list)
    target: dict[str, int] = field(default_factory=dict)
    core_held: int = 0
    core_target: int = 0
    slice_val: float = 0.0
    held_sats: dict[str, int] = field(default_factory=dict)
    excluded: set[str] = field(default_factory=set)
    kept: list[str] = field(default_factory=list)
    retained: list[str] = field(default_factory=list)
    pending_drops: list[str] = field(default_factory=list)

    def px(self, sym: str) -> float:
        return float(self.ref[sym])

    def rank(self, sym: str) -> int:
        return self.ranks.get(sym, 999)

    def rank_label(self, sym: str) -> str:
        return str(self.ranks.get(sym, 'NA'))

    def warn(self, msg: str) -> None:
        log(f"WARNING: {msg}")
        self.warnings.append(msg)

    def cap_breached(self, sym: str, qty: int) -> bool:
        add = fin_exposure(sym, qty, self.px(sym))
        return add > 0 and self.total_capital > 0 and \
            (self.fin_value + add) / self.total_capital > MAX_FINANCIALS_LOOKTHROUGH

    def sell(self, sym: str, qty: int, reason: str) -> None:
        self.sells.append((sym, qty, reason))
        self.fin_value -= fin_exposure(sym, qty, self.px(sym))

    def commit_buy(self, sym: str, qty: int, desired: int, reason: str) -> None:
        value = qty * self.px(sym)
        self.cash -= value + delivery_cost('BUY', value, sym == CORE)
        self.fin_value += fin_exposure(sym, qty, self.px(sym))
        if qty < desired:
            self.warn(f"{sym} buy reduced from {desired} to {qty} shares to fit available cash")
        self.buys.append((sym, qty, reason))


def plan_core(p: Plan) -> None:
    core_px = p.px(CORE)
    p.core_held = p.holdings.get(CORE, 0)
    p.core_target = int((CORE_TARGET_FRACTION * p.total_capital) // core_px)
    if CORE in p.flagged and p.core_target != p.core_held:
        p.warn(f"{CORE} flagged for possible corporate action; core order suppressed")
        p.core_target = p.core_held
    if CORE in p.no_buy and p.core_target > p.core_held:
        p.warn(f"{CORE} had a >20% adjusted move; core buy suppressed")
        p.core_target = p.core_held
    if p.core_target != p.core_held and abs(p.core_target - p.core_held) * core_px < MIN_TRADE_VALUE:
        p.core_target = p.core_held
    if p.core_target < p.core_held:
        p.sell(CORE, p.core_held - p.core_target, 'core ETF trim to 50% target')
    p.target[CORE] = p.core_target
    p.slice_val = (p.total_capital - p.core_target * core_px) / SATELLITE_SLOTS


def plan_exits(p: Plan, state: dict) -> None:
    p.held_sats = {s: q for s, q in p.holdings.items() if s != CORE}
    today = now_ist().strftime('%Y-%m-%d')
    counted_today = state.get('streak_updated') == today
    prev_streaks = {s: int(v) for s, v in state.get('below_rank_streak', {}).items()}
    streaks = {s: (prev_streaks.get(s, 0) if counted_today else prev_streaks.get(s, 0) + 1)
               if p.rank(s) > FLOOR_RANK else 0
               for s in p.held_sats}
    state['below_rank_streak'] = streaks
    state['streak_updated'] = today
    avg_costs = state.get('avg_cost', {})
    for s in sorted(p.held_sats):
        reason: str | None = None
        if s not in avg_costs:
            p.warn(f"{s} missing avg_cost in state; loss-stop check skipped")
        elif p.px(s) < float(avg_costs[s]) * (1 - LOSS_STOP):
            reason = 'position stop -20%'
        if reason is None and streaks[s] >= FLOOR_STREAK:
            reason = 'persistent signal deterioration'
        if reason is None:
            continue
        if s in p.flagged:
            p.warn(f"{s} flagged for possible corporate action; exit ({reason}) suppressed")
            continue
        p.sell(s, p.held_sats[s], reason)
        p.excluded.add(s)
    for s in p.excluded:
        del p.held_sats[s]

    p.kept = sorted([s for s in p.held_sats if p.rank(s) <= KEEP_RANK], key=p.rank)[:SATELLITE_SLOTS]
    p.pending_drops = sorted([s for s in p.held_sats if s not in p.kept], key=p.rank)
    for s in [d for d in p.pending_drops if d in p.flagged]:
        p.warn(f"{s} flagged for possible corporate action; sell suppressed, position retained")
        p.pending_drops.remove(s)
        p.retained.append(s)
    if len(p.kept) + len(p.retained) >= SATELLITE_SLOTS:
        for s in p.pending_drops:
            p.sell(s, p.held_sats[s], f"rank {p.rank_label(s)}, excess satellite beyond {SATELLITE_SLOTS} slots")
        p.pending_drops = []

    for sym, qty, _ in p.sells:
        value = qty * p.px(sym)
        p.cash += value - delivery_cost('SELL', value, sym == CORE)


def plan_entries(p: Plan) -> None:
    core_px = p.px(CORE)
    if p.core_target > p.core_held:
        desired = p.core_target - p.core_held
        qty = buy_qty_affordable(core_px, p.cash, desired, True)
        if qty * core_px < MIN_TRADE_VALUE:
            p.warn(f"{CORE} buy of {desired} shares unaffordable with Rs.{p.cash:.2f} available; skipped")
            p.target[CORE] = p.core_held
        elif p.cap_breached(CORE, qty):
            p.warn(f"{CORE} buy skipped: financials look-through would exceed {MAX_FINANCIALS_LOOKTHROUGH:.0%} cap")
            p.target[CORE] = p.core_held
        else:
            p.commit_buy(CORE, qty, desired, 'core ETF, 50% capital target')
            p.target[CORE] = p.core_held + qty

    for s in p.kept:
        qty_held = p.held_sats[s]
        px = p.px(s)
        top_up = int(p.slice_val // px) - qty_held
        got = 0
        if s not in p.flagged and s not in p.no_buy and top_up > 0 and top_up * px >= MIN_TRADE_VALUE:
            afford = buy_qty_affordable(px, p.cash, top_up)
            if afford * px >= MIN_TRADE_VALUE:
                if p.cap_breached(s, afford):
                    p.warn(f"{s} top-up skipped: financials look-through would exceed {MAX_FINANCIALS_LOOKTHROUGH:.0%} cap")
                else:
                    p.commit_buy(s, afford, top_up, f"top-up held satellite, rank {p.rank(s)}")
                    got = afford
        p.target[s] = qty_held + got
    for s in p.retained:
        p.target[s] = p.held_sats[s]

    slots_free = max(0, SATELLITE_SLOTS - len(p.kept) - len(p.retained) - len(p.pending_drops))
    for s in p.scores.index:
        if slots_free <= 0 and not p.pending_drops:
            break
        if s in p.target or s in p.held_sats or s in p.flagged or s in p.no_buy or s in p.excluded:
            continue
        px = p.px(s)
        if px > p.slice_val:
            log(f"WARNING: skipping {s}: 1 share Rs.{px:.2f} exceeds slice Rs.{p.slice_val:.2f}")
            continue
        desired = int(p.slice_val // px)
        if desired * px < MIN_TRADE_VALUE:
            log(f"WARNING: skipping {s}: position Rs.{desired * px:.2f} below minimum Rs.{MIN_TRADE_VALUE:.0f}")
            continue
        if slots_free > 0:
            qty = buy_qty_affordable(px, p.cash, desired)
            if qty * px < MIN_TRADE_VALUE:
                log(f"WARNING: skipping {s}: affordable position Rs.{qty * px:.2f} below minimum Rs.{MIN_TRADE_VALUE:.0f}")
                continue
            if p.cap_breached(s, qty):
                p.warn(f"{s} buy skipped: financials look-through would exceed {MAX_FINANCIALS_LOOKTHROUGH:.0%} cap")
                continue
            p.commit_buy(s, qty, desired, f"new satellite entry, rank {p.rank(s)}")
            p.target[s] = qty
            slots_free -= 1
            continue
        out = p.pending_drops[-1]
        out_score = float(p.scores[out]) if out in p.scores.index else float('-inf')
        if float(p.scores[s]) <= out_score + SWAP_SCORE_MARGIN:
            break
        out_value = p.held_sats[out] * p.px(out)
        proceeds = out_value - delivery_cost('SELL', out_value)
        qty = buy_qty_affordable(px, p.cash + proceeds, desired)
        if qty * px < MIN_TRADE_VALUE:
            log(f"NOTE: replacement of {out} by {s} not affordable; next candidate considered")
            continue
        out_fin = fin_exposure(out, p.held_sats[out], p.px(out))
        add_fin = fin_exposure(s, qty, px)
        if add_fin > 0 and p.total_capital > 0 and \
                (p.fin_value - out_fin + add_fin) / p.total_capital > MAX_FINANCIALS_LOOKTHROUGH:
            p.warn(f"{s} replacement buy skipped: financials look-through would exceed {MAX_FINANCIALS_LOOKTHROUGH:.0%} cap")
            continue
        p.pending_drops.pop()
        p.sell(out, p.held_sats[out], f"fell to rank {p.rank_label(out)}, replaced by {s}")
        p.cash += proceeds
        p.commit_buy(s, qty, desired,
                     f"replacement entry, rank {p.rank(s)}, score margin {float(p.scores[s]) - out_score:.2f}")
        p.target[s] = qty
    for s in p.pending_drops:
        log(f"NOTE: {s} rank {p.rank_label(s)} is below {KEEP_RANK} but no qualifying replacement fits; retained")
        p.target[s] = p.held_sats[s]


def build_plan(scores: pd.Series, ref: pd.Series, state: dict, capital_cash: float,
               flagged: set[str], regime: str, no_buy: frozenset[str] = frozenset()) -> dict:
    holdings = {s: int(q) for s, q in state.get('holdings', {}).items() if q > 0}
    unpriced = sorted(s for s in holdings if s not in ref.index)
    if unpriced:
        raise ValueError(f"held tickers have no usable price data today: {unpriced}; refusing to plan on understated capital")
    total_capital = capital_cash + sum(q * float(ref[s]) for s, q in holdings.items())
    p = Plan(scores=scores, ref=ref, holdings=holdings, total_capital=total_capital, cash=capital_cash,
             flagged=flagged, no_buy=no_buy, ranks={s: i + 1 for i, s in enumerate(scores.index)},
             fin_value=sum(fin_exposure(s, q, float(ref[s])) for s, q in holdings.items()))
    if total_capital > 0 and p.fin_value / total_capital > MAX_FINANCIALS_LOOKTHROUGH:
        p.warn(f"financials look-through {p.fin_value / total_capital:.0%} exceeds cap {MAX_FINANCIALS_LOOKTHROUGH:.0%}")
    plan_core(p)
    plan_exits(p, state)
    plan_entries(p)

    ordered = [('SELL', sym, qty, reason) for sym, qty, reason in p.sells] + \
              [('BUY', sym, qty, reason) for sym, qty, reason in p.buys]
    order_dicts = []
    for action, sym, qty, reason in ordered:
        value = qty * p.px(sym)
        order_dicts.append({
            'action': action, 'symbol': sym, 'qty': qty,
            'ref_price': round(p.px(sym), 2), 'est_value': round(value, 2),
            'est_cost': round(delivery_cost(action, value, sym == CORE), 2), 'reason': reason,
        })
    return {
        'generated': now_ist().isoformat(),
        'regime': regime,
        'capital': round(total_capital, 2),
        'cash_available': round(capital_cash, 2),
        'orders': order_dicts,
        'target_portfolio': {s: q for s, q in p.target.items() if q > 0},
        'expected_cash': round(p.cash, 2),
        'warnings': p.warnings,
        'scores': {s: round(float(scores[s]), 4) for s in list(scores.index)[:6]},
    }


def format_ticket(plan: dict) -> str:
    lines = [
        f"SMALL ACCOUNT TRADE TICKET {plan['generated'][:10]}",
        f"Regime: {plan['regime'].upper()} | Capital: Rs.{plan['capital']:,.2f}",
    ]
    if not plan['orders']:
        lines.append("No trades required today.")
    for i, o in enumerate(plan['orders'], 1):
        lines.append(
            f"{i}. {o['action']} {o['qty']} {o['symbol']} @ ~Rs.{o['ref_price']:,.2f} "
            f"= Rs.{o['est_value']:,.2f} (est cost Rs.{o['est_cost']:.2f}): {o['reason']}"
        )
    for w in plan.get('warnings', []):
        lines.append(f"WARNING: {w}")
    lines.append(f"Total estimated cost: Rs.{sum(o['est_cost'] for o in plan['orders']):.2f}")
    lines.append(f"Expected residual cash: Rs.{plan['expected_cash']:,.2f}")
    lines.append("Execution: quantshield.live.executor (LIMIT only). The planner never places orders.")
    return '\n'.join(lines)


def write_snapshot(state: dict, ref: pd.Series, capital_cash: float) -> None:
    ts = ref.name
    if isinstance(ts, pd.Timestamp) and ts.date() != now_ist().date():
        log(f"WARNING: snapshot skipped; latest close dated {ts.date()}, not today: market closed or data stale")
        return
    track = {'inception': None, 'snapshots': []}
    if os.path.exists(TRACK_PATH):
        track = load_json(TRACK_PATH)
        if track is None:
            log(f"WARNING: snapshot skipped; track record unreadable: {TRACK_PATH}")
            return
    holdings = {s: int(q) for s, q in state.get('holdings', {}).items() if q > 0}
    unpriced = sorted(s for s in holdings if s not in ref.index)
    if unpriced:
        log(f"WARNING: snapshot skipped; held tickers missing price data: {unpriced}")
        return
    core_px = float(ref[CORE])
    pv = capital_cash + sum(q * float(ref[s]) for s, q in holdings.items())
    if not track.get('inception'):
        track['inception'] = {
            'date': now_ist().strftime('%Y-%m-%d'),
            'capital': round(pv, 2),
            'units': round(pv / core_px, 6),
        }
    today = now_ist().strftime('%Y-%m-%d')
    track['snapshots'] = [s for s in track['snapshots'] if s.get('date') != today]
    track['snapshots'].append({
        'date': today,
        'portfolio_value': round(pv, 2),
        'cash': round(capital_cash, 2),
        'niftybees_benchmark_value': round(track['inception']['units'] * core_px, 2),
    })
    atomic_write_json(TRACK_PATH, sanitize(track))
    log(f"Snapshot appended to {TRACK_PATH}")


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description='Small-account planner: writes trade tickets, never places orders')
    parser.add_argument('--capital', type=float)
    parser.add_argument('--no-notify', action='store_true')
    parser.add_argument('--snapshot', action='store_true')
    args = parser.parse_args()

    capital_cash = args.capital
    snapshot_only = args.snapshot
    if capital_cash is None:
        capital_cash = fetch_live_cash()
        if capital_cash is None:
            if snapshot_only:
                log("NOTE: live capital unavailable; snapshot-only fallback using state cash + priced holdings")
            else:
                log("ERROR: could not fetch live cash; pass --capital explicitly")
                sys.exit(1)
        else:
            log(f"Live equity available cash: Rs.{capital_cash:,.2f}")
    if capital_cash is not None and capital_cash < 0:
        log("ERROR: capital must be non-negative")
        sys.exit(1)

    close, raw_close = download_close([CORE] + INDIA_TICKERS)
    if close.empty or CORE not in close.columns or close[CORE].dropna().empty:
        log("ERROR: NIFTYBEES.NS price data missing; aborting")
        sys.exit(1)
    unfilled = close
    close = close.ffill()
    raw_close = raw_close.ffill()
    dead = [c for c in close.columns if close[c].isna().all() or float(close[c].iloc[-1]) <= 0]
    stale = [c for c in unfilled.columns if c not in dead and unfilled[c].iloc[-(STALE_SESSIONS + 1):].isna().all()]
    if dead:
        log(f"WARNING: dropping tickers with missing or invalid data: {dead}")
    if stale:
        log(f"WARNING: dropping stale tickers with no fresh prints in last {STALE_SESSIONS + 1} sessions: {stale}")
    if dead or stale:
        close = close.drop(columns=dead + stale)
        raw_close = raw_close.drop(columns=[c for c in dead + stale if c in raw_close.columns])
    if CORE not in close.columns:
        log("ERROR: NIFTYBEES.NS data invalid; aborting")
        sys.exit(1)
    if snapshot_only:
        state = load_state()
        cash = capital_cash if capital_cash is not None else float(state.get('cash', 0.0))
        write_snapshot(state, close.iloc[-1], cash)
        return
    sats = [c for c in close.columns if c != CORE]
    sat_close = close[sats].dropna()
    if sat_close.empty or len(sats) < 3:
        log("ERROR: insufficient satellite data; aborting")
        sys.exit(1)

    macro_close, _ = download_close(INDIA_MACRO_TICKERS)
    if macro_close.empty:
        log("ERROR: macro data download failed; aborting")
        sys.exit(1)
    macro_close = macro_close.ffill()
    dead_macro = [c for c in macro_close.columns if macro_close[c].isna().all()]
    if dead_macro:
        log(f"WARNING: dropping macro tickers with no data: {dead_macro}")
        macro_close = macro_close.drop(columns=dead_macro)
    macro_close = macro_close.dropna()
    if macro_close.empty:
        log("ERROR: no usable macro data after cleaning; aborting")
        sys.exit(1)

    adj_jump = close.pct_change().abs() > 0.20
    raw_jump = raw_close.pct_change().abs() > 0.20
    crash_flagged = frozenset(c for c in close.columns if adj_jump[c].any())
    corp_flagged = {c for c in close.columns if c in raw_jump.columns and
                    (raw_jump[c].iloc[-CORP_ACTION_SESSIONS:] &
                     ~adj_jump[c].iloc[-CORP_ACTION_SESSIONS:]).any()}
    for c in sorted(crash_flagged):
        log(f"WARNING: {c} had a day-over-day move >20%: possible corporate action or shock; excluded from BUYs")
    for c in sorted(corp_flagged):
        log(f"WARNING: {c} raw price gapped >20% without an adjusted move in the last {CORP_ACTION_SESSIONS} "
            f"sessions: split/bonus suspected; exits suppressed; verify avg_cost and holdings in {STATE_PATH}")

    regime, confidence, _ = india_detect_regime(macro_close)
    log(f"Regime: {regime.upper()} ({confidence:.0%} confidence)")

    scores = compute_scores(sat_close, macro_close, regime)
    ref = close.iloc[-1]
    state = load_state()
    try:
        plan = build_plan(scores, ref, state, capital_cash, corp_flagged, regime, no_buy=crash_flagged)
    except ValueError as exc:
        log(f"ERROR: {exc}")
        sys.exit(1)
    atomic_write_json(PLAN_PATH, sanitize(plan))
    log(f"Plan written to {PLAN_PATH}")
    atomic_write_json(STATE_PATH, sanitize(state))

    ticket = format_ticket(plan)
    print(ticket)
    if not args.no_notify:
        notify(ticket)


if __name__ == '__main__':
    main()
