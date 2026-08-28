import argparse
import json
from collections import defaultdict
from datetime import datetime

import numpy as np

from quantshield.intraday.stats import BOOTSTRAP_DESCRIPTION, adjusted_deltas, bootstrap_p, buy_and_hold_pct
from quantshield.paths import INTRADAY
from quantshield.utils import IST, atomic_write_json, load_json, log, read_jsonl

TRACK_PATH = str(INTRADAY / 'paper_track_record.jsonl')
GATE_PATH = str(INTRADAY / 'gate.json')
OUT_PATH = str(INTRADAY / 'scoreboard.json')
GATE_MIN_SESSIONS = 60
GATE_P = 0.05


def gate_terms(gate_path: str | None = None) -> dict:
    gate = load_json(gate_path or GATE_PATH, {}) or {}
    primary = (gate.get('primary_hypothesis') or {}).get('name')
    min_sessions = int((gate.get('benchmark_and_test') or {}).get('min_sessions', GATE_MIN_SESSIONS))
    return {'primary_arm': primary, 'min_sessions': min_sessions, 'p_threshold': GATE_P}


def arm_stats(records: list[dict], min_sessions: int = GATE_MIN_SESSIONS, primary: bool = True) -> dict:
    scored = [r for r in records if not r.get('blind')]
    blind = len(records) - len(scored)
    triggered = [r for r in scored if r.get('triggered')]
    net = np.array([r.get('net', 0.0) for r in triggered], dtype=float)
    costs = np.array([r.get('costs', 0.0) for r in triggered], dtype=float)
    adj = adjusted_deltas(scored)
    p = bootstrap_p(adj) if adj.size >= 3 else None
    hold = buy_and_hold_pct(scored)
    guard_ok = hold is not None and hold > 0
    gate_open = bool(
        primary
        and len(scored) >= min_sessions
        and p is not None and p < GATE_P
        and guard_ok
    )
    return {
        'primary': primary,
        'sessions_scored': len(scored),
        'sessions_blind': blind,
        'sessions_remaining_for_gate': max(0, min_sessions - len(scored)),
        'triggered': len(triggered),
        'win_rate_pct': round(float((net > 0).sum()) / net.size * 100, 1) if net.size else None,
        'net_total_rs': round(float(net.sum()), 2),
        'costs_total_rs': round(float(costs.sum()), 2),
        'adjusted_delta_mean_pct': round(float(adj.mean()), 4) if adj.size else None,
        'bootstrap_p_one_sided': round(p, 4) if p is not None else None,
        'bench_hold_ret_pct': round(hold, 2) if hold is not None else None,
        'directional_guard_ok': guard_ok,
        'gate_open': gate_open,
    }


def build(track_path: str | None = None, gate_path: str | None = None) -> dict:
    terms = gate_terms(gate_path)
    by_arm: dict[str, list[dict]] = defaultdict(list)
    for r in read_jsonl(track_path or TRACK_PATH):
        by_arm[r.get('arm', 'unknown')].append(r)
    arms = {
        arm: arm_stats(rows, terms['min_sessions'], arm == terms['primary_arm'])
        for arm, rows in sorted(by_arm.items())
    }
    primary = arms.get(terms['primary_arm'], {})
    return {
        'generated': datetime.now(IST).isoformat(),
        'arms': arms,
        'gate': {
            **terms,
            'test': BOOTSTRAP_DESCRIPTION,
            'status': 'OPEN' if primary.get('gate_open') else 'CLOSED',
            'note': 'Gate evidence is live paper sessions of the primary arm only. See data/intraday/gate.json.',
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--notify', action='store_true')
    parser.add_argument('--out', default=OUT_PATH)
    args = parser.parse_args()
    board = build()
    atomic_write_json(args.out, board)
    print(json.dumps(board, indent=2))
    if args.notify and board['arms']:
        try:
            from quantshield.live.notify import notify
            min_sessions = board['gate']['min_sessions']
            lines = [f"ORB scoreboard {board['generated'][:10]}"]
            for arm, s in board['arms'].items():
                lines.append(
                    f"{arm}: {s['sessions_scored']}/{min_sessions} sessions, "
                    f"net Rs.{s['net_total_rs']}, p={s['bootstrap_p_one_sided']}, "
                    f"gate {'OPEN' if s['gate_open'] else 'closed'}"
                )
            notify('\n'.join(lines), level='info')
        except Exception as exc:
            log(f'notify failed: {exc}', 'scoreboard')


if __name__ == '__main__':
    main()
