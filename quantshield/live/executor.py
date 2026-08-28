import argparse
import fcntl
import math
import os
import sys
import time
from datetime import datetime
from typing import IO

from dotenv import load_dotenv

from quantshield.broker.zerodha import get_kite
from quantshield.config import INDIA_TICKERS
from quantshield.costs import delivery_cost
from quantshield.live.notify import notify
from quantshield.paths import DATA, JOURNAL, PORTFOLIO
from quantshield.utils import append_jsonl, atomic_write_json, load_json, now_ist
from quantshield.utils import log as _log

TAG = 'execute'
MAX_PLAN_AGE_H = 6
MAX_ORDER_VALUE = 3000.0
MAX_DAY_TURNOVER = 6000.0
MAX_ORDERS_PER_DAY = 6
LIMIT_BAND = 0.01
TICK = 0.05
ORDER_SLEEP = 1.2
POLL_PRIMARY_S = 90
POLL_MODIFIED_S = 60
POLL_CANCEL_S = 12
POLL_STEP_S = 3
CORE = 'NIFTYBEES.NS'
TERMINAL_STATUSES = ('COMPLETE', 'REJECTED', 'CANCELLED')
UNIVERSE = frozenset([CORE] + list(INDIA_TICKERS))

PLAN_PATH = str(PORTFOLIO / 'small_account_plan.json')
STATE_PATH = str(PORTFOLIO / 'small_account_state.json')
JOURNAL_PATH = str(PORTFOLIO / 'execution_journal.json')
TRADE_LOG_PATH = str(JOURNAL / 'trade_log.jsonl')
KILL_FILE = str(DATA / 'KILL')
LOCK_PATH = str(PORTFOLIO / '.execute.lock')


def log(msg: str) -> None:
    _log(msg, TAG)


def acquire_lock() -> IO[str] | None:
    os.makedirs(os.path.dirname(LOCK_PATH), exist_ok=True)
    fh = open(LOCK_PATH, 'w')
    try:
        fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        fh.close()
        return None
    return fh


def zsym(symbol: str) -> str:
    return symbol[:-3] if symbol.endswith('.NS') else symbol


def limit_price(ref: float, action: str, band: float) -> float:
    px = ref * (1 + band) if action == 'BUY' else ref * (1 - band)
    ticks = math.ceil(px / TICK) if action == 'BUY' else math.floor(px / TICK)
    return round(ticks * TICK, 2)


def read_or_abort(path: str, default: object) -> object:
    if not os.path.exists(path):
        return default
    data = load_json(path)
    if data is None:
        log(f"unreadable JSON at {path}; refusing to run")
        notify(f"Execution aborted: {os.path.basename(path)} is unreadable", level='warning')
        sys.exit(3)
    return data


def broker_snapshot(kite: object) -> tuple[dict[str, int], dict[str, float]]:
    qty: dict[str, int] = {}
    avg_px: dict[str, float] = {}
    for h in kite.holdings():
        s = h['tradingsymbol']
        qty[s] = qty.get(s, 0) + int(h['quantity']) + int(h.get('t1_quantity') or 0)
        avg_px[s] = float(h.get('average_price') or 0.0)
    for p in kite.positions().get('net', []):
        if p.get('product') == 'CNC':
            day_net = int(p.get('day_buy_quantity') or 0) - int(p.get('day_sell_quantity') or 0)
            if day_net:
                qty[p['tradingsymbol']] = qty.get(p['tradingsymbol'], 0) + day_net
    return qty, avg_px


def wait_fill(kite: object, order_id: str, seconds: float) -> tuple[str, int, float]:
    status, filled, avg = 'OPEN', 0, 0.0
    deadline = time.time() + seconds
    while time.time() < deadline:
        try:
            last = kite.order_history(order_id)[-1]
            status = last.get('status', 'OPEN')
            filled = int(last.get('filled_quantity') or 0)
            avg = float(last.get('average_price') or 0.0)
        except Exception as exc:
            log(f"order poll failed: {exc}")
        if status in TERMINAL_STATUSES:
            return status, filled, avg
        time.sleep(POLL_STEP_S)
    return status, filled, avg


def find_live_order(kite: object, tsym: str, action: str, qty: int, px: float) -> str | None:
    for od in kite.orders():
        if (od.get('tradingsymbol') == tsym and od.get('transaction_type') == action
                and int(od.get('quantity') or 0) == qty
                and abs(float(od.get('price') or 0.0) - px) < TICK / 2
                and od.get('status') not in ('REJECTED', 'CANCELLED')):
            return str(od.get('order_id'))
    return None


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description='Execute the small-account plan via Zerodha LIMIT CNC orders')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    auto = os.environ.get('AUTO_EXECUTE', '') == 'true'
    live_env = os.environ.get('ZERODHA_LIVE_MODE', '') == 'true'
    live = auto and live_env and not args.dry_run
    if not live:
        reason = '--dry-run flag' if args.dry_run else ('AUTO_EXECUTE != true' if not auto else 'ZERODHA_LIVE_MODE != true')
        log(f"DRY RUN ({reason})")

    if os.path.exists(KILL_FILE):
        log("KILL file present; refusing to run")
        notify("Execution halted: data/KILL present. Remove it to resume auto-trading.", level='warning')
        sys.exit(2)

    lock = acquire_lock()
    if lock is None:
        log("another executor instance holds the lock; exiting")
        sys.exit(5)
    try:
        _run(live)
    finally:
        fcntl.flock(lock, fcntl.LOCK_UN)
        lock.close()


def _run(live: bool) -> None:
    today = now_ist().strftime('%Y-%m-%d')
    plan = load_json(PLAN_PATH)
    if not plan or str(plan.get('generated', ''))[:10] != today:
        log("no plan generated today; nothing to do")
        sys.exit(0)
    orders = plan.get('orders', [])
    if not orders:
        log("plan has no orders; nothing to do")
        sys.exit(0)
    age_h = (now_ist() - datetime.fromisoformat(plan['generated'])).total_seconds() / 3600
    if age_h > MAX_PLAN_AGE_H:
        log(f"plan is {age_h:.1f}h old; refusing")
        notify(f"Execution skipped: plan is {age_h:.1f}h old (limit {MAX_PLAN_AGE_H}h)", level='warning')
        sys.exit(0)

    kite = get_kite()
    if kite is None:
        notify("Zerodha access token expired; run the daily login before 09:25 IST", level='warning')
        sys.exit(3)

    state = read_or_abort(STATE_PATH, {'holdings': {}, 'cash': 0.0})
    try:
        broker, _ = broker_snapshot(kite)
        cash = float(kite.margins(segment='equity')['available']['live_balance'])
    except Exception as exc:
        log(f"broker read failed: {exc}")
        notify(f"Execution aborted: broker read failed ({exc})", level='warning')
        sys.exit(3)

    journal = read_or_abort(JOURNAL_PATH, [])
    done = {(e.get('date'), e.get('symbol'), e.get('action')) for e in journal}
    sells = [o for o in orders if o['action'] == 'SELL']
    buys = [o for o in orders if o['action'] == 'BUY']
    for o in sells:
        if (today, o['symbol'], 'SELL') in done:
            continue
        bq, sq = broker.get(zsym(o['symbol']), 0), int(state.get('holdings', {}).get(o['symbol'], 0))
        if bq != sq or bq < int(o['qty']):
            log(f"reconcile mismatch {o['symbol']}: broker={bq} state={sq} sell_qty={o['qty']}")
            notify(f"Execution aborted: holdings mismatch on {o['symbol']} (broker {bq} vs state {sq})", level='warning')
            sys.exit(4)
    prior = [e for e in journal if e.get('date') == today and e.get('order_id')]
    turnover = sum(float(e.get('qty', 0)) * float(e.get('limit_px', 0)) for e in prior)
    placed = len(prior)
    report: list[str] = []
    fills: dict[str, list[tuple[str, int, float]]] = {}

    def save() -> None:
        atomic_write_json(JOURNAL_PATH, journal)

    def journal_entry(sym: str, action: str, qty: int, status: str, order_id: str | None, px: float) -> dict:
        entry = {'date': today, 'plan_generated': plan['generated'], 'symbol': sym, 'action': action,
                 'qty': qty, 'order_id': order_id, 'limit_px': px, 'status': status,
                 'filled_qty': 0, 'avg_price': 0.0, 'ts': now_ist().isoformat()}
        journal.append(entry)
        save()
        return entry

    for o in sells + buys:
        if os.path.exists(KILL_FILE):
            log("KILL file appeared mid-run; halting remaining orders")
            notify("Execution halted mid-run: data/KILL present; remaining plan orders not placed", level='warning')
            break
        sym, action, qty, ref = o['symbol'], o['action'], int(o['qty']), float(o['ref_price'])
        if (today, sym, action) in done:
            log(f"skip {action} {qty} {sym}: {action} {sym} already journaled today")
            continue
        px = limit_price(ref, action, LIMIT_BAND)
        etf = sym == CORE
        if action == 'BUY':
            afford = qty
            while afford > 0 and afford * px + delivery_cost('BUY', afford * px, etf) > cash:
                afford -= 1
            if afford < qty:
                report.append(f"{sym} BUY scaled {qty}->{afford} to fit cash Rs.{cash:.2f}")
                qty = afford
            if qty == 0:
                if live:
                    journal_entry(sym, action, int(o['qty']), 'SKIPPED_CASH', None, px)
                    done.add((today, sym, action))
                continue
        value = qty * px
        if value > MAX_ORDER_VALUE or turnover + value > MAX_DAY_TURNOVER or placed >= MAX_ORDERS_PER_DAY:
            why = 'order value cap' if value > MAX_ORDER_VALUE else ('day turnover cap' if turnover + value > MAX_DAY_TURNOVER else 'max orders/day')
            report.append(f"{action} {qty} {sym} skipped: {why}")
            if live:
                journal_entry(sym, action, qty, 'SKIPPED_GUARDRAIL', None, px)
                done.add((today, sym, action))
            continue
        if not live:
            report.append(f"DRY: would {action} {qty} {zsym(sym)} LIMIT Rs.{px:.2f} (~Rs.{value:.2f})")
            turnover += value
            placed += 1
            continue
        entry = journal_entry(sym, action, qty, 'PLACING', None, px)
        done.add((today, sym, action))
        try:
            order_id = kite.place_order(variety='regular', exchange='NSE', tradingsymbol=zsym(sym),
                                        transaction_type=action, quantity=qty, product='CNC',
                                        order_type='LIMIT', price=px, validity='DAY')
        except Exception as exc:
            log(f"place_order failed for {sym}: {exc}")
            try:
                order_id = find_live_order(kite, zsym(sym), action, qty, px)
            except Exception as scan_exc:
                log(f"orders() reconcile failed: {scan_exc}")
                entry.update({'status': 'PLACEMENT_UNVERIFIED', 'ts': now_ist().isoformat()})
                save()
                notify(f"{action} {qty} {zsym(sym)} placement unverified after {exc}; check Kite immediately",
                       level='warning')
                report.append(f"{action} {qty} {sym} PLACEMENT_UNVERIFIED: {exc}")
                continue
            if order_id is None:
                entry.update({'status': 'FAILED', 'ts': now_ist().isoformat()})
                save()
                report.append(f"{action} {qty} {sym} FAILED to place: {exc}")
                continue
            log(f"adopted live order {order_id} for {sym} after ambiguous place_order failure")
        placed += 1
        turnover += value
        entry.update({'status': 'PENDING', 'order_id': order_id, 'ts': now_ist().isoformat()})
        save()
        status, filled, avg = wait_fill(kite, order_id, POLL_PRIMARY_S)
        note = ''
        if status not in TERMINAL_STATUSES:
            px2 = limit_price(ref, action, 2 * LIMIT_BAND)
            try:
                kite.modify_order(variety='regular', order_id=order_id, price=px2)
                entry['limit_px'] = px2
                note = 'price modified once'
                log(f"{sym} still open; modified to Rs.{px2:.2f}")
            except Exception as exc:
                log(f"modify_order failed for {sym}: {exc}")
            status, filled, avg = wait_fill(kite, order_id, POLL_MODIFIED_S)
        if status not in TERMINAL_STATUSES:
            cancel_err: Exception | None = None
            try:
                kite.cancel_order(variety='regular', order_id=order_id)
            except Exception as exc:
                cancel_err = exc
                log(f"cancel_order failed for {sym}: {exc}")
            status, filled, avg = wait_fill(kite, order_id, POLL_CANCEL_S)
            if status in ('CANCELLED', 'REJECTED'):
                status = 'UNFILLED'
                notify(f"{action} {qty} {zsym(sym)} unfilled after modify+cancel window"
                       + (f" ({filled} filled before cancel)" if filled else ""), level='warning')
            elif status != 'COMPLETE':
                status = 'CANCEL_UNVERIFIED'
                detail = f": {cancel_err}" if cancel_err else ""
                notify(f"{action} {qty} {zsym(sym)} order {order_id} may still be live at broker "
                       f"(cancel unverified{detail}); check Kite immediately", level='warning')
        entry.update({'status': status, 'filled_qty': filled, 'avg_price': round(avg, 2), 'ts': now_ist().isoformat()})
        save()
        if filled > 0 and avg > 0:
            fills.setdefault(sym, []).append((action, filled, avg))
            fill_value = filled * avg
            cash += -fill_value - delivery_cost('BUY', fill_value, etf) if action == 'BUY' else fill_value - delivery_cost('SELL', fill_value, etf)
            append_jsonl(TRADE_LOG_PATH, {
                'date': today, 'symbol': sym, 'action': action, 'qty': filled,
                'plan_ref_price': ref, 'limit_px': entry['limit_px'], 'fill_px': round(avg, 2),
                'slippage_bps': round((avg - ref) / ref * 10000 * (1 if action == 'BUY' else -1), 1),
                'est_cost': round(delivery_cost(action, fill_value, etf), 2), 'notes': f"{status} {note}".strip()})
        report.append(f"{action} {qty} {zsym(sym)} lim Rs.{entry['limit_px']:.2f} -> {status}, filled {filled} @ Rs.{avg:.2f}")
        time.sleep(ORDER_SLEEP)

    refresh_failed = False
    if live and fills:
        try:
            broker, broker_avg = broker_snapshot(kite)
            live_cash = float(kite.margins(segment='equity')['available']['live_balance'])
            old_hold = {s: int(q) for s, q in state.get('holdings', {}).items()}
            avg_cost = {s: float(v) for s, v in state.get('avg_cost', {}).items()}
            for sym, fl in fills.items():
                bq = sum(f[1] for f in fl if f[0] == 'BUY')
                bv = sum(f[1] * f[2] for f in fl if f[0] == 'BUY')
                if bq > 0:
                    oq, oa = old_hold.get(sym, 0), avg_cost.get(sym, 0.0)
                    avg_cost[sym] = round((oq * oa + bv) / (oq + bq), 2) if oa > 0 else round(bv / bq, 2)
            held = {f"{s}.NS": q for s, q in broker.items() if q > 0 and f"{s}.NS" in UNIVERSE}
            foreign = sorted(s for s, q in broker.items() if q > 0 and f"{s}.NS" not in UNIVERSE)
            if foreign:
                log(f"ignoring non-strategy holdings in account: {foreign}")
            state['holdings'] = held
            state['avg_cost'] = {s: round(avg_cost.get(s) or broker_avg.get(zsym(s), 0.0), 2) for s in held}
            state['cash'] = round(live_cash, 2)
            state['updated'] = now_ist().isoformat()
            atomic_write_json(STATE_PATH, state)
            log(f"state refreshed from broker: cash Rs.{live_cash:.2f}, holdings {held}")
        except Exception as exc:
            refresh_failed = True
            log(f"post-trade state refresh failed: {exc}")
            notify(f"Execution done but state refresh failed: {exc}", level='warning')

    if not report:
        report.append("nothing to do: all plan orders already journaled today")
    header = f"Execution report {today} ({'LIVE' if live else 'DRY RUN'})"
    body = '\n'.join([header] + report)
    print(body)
    if live:
        notify(body)
    sys.exit(6 if refresh_failed else 0)


if __name__ == '__main__':
    main()
