import json
import math
import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytz

IST = pytz.timezone('Asia/Kolkata')


def log(msg: str, tag: str = '') -> None:
    prefix = f'[{tag}] ' if tag else ''
    print(f'{prefix}{msg}', file=sys.stderr)


def now_ist() -> datetime:
    return datetime.now(IST).replace(tzinfo=None)


def rank_normalize(series: pd.Series) -> pd.Series:
    if series.nunique() <= 1:
        return pd.Series(0.0, index=series.index)
    return 2 * series.rank(pct=True) - 1


def sanitize(obj: object) -> object:
    if isinstance(obj, dict):
        return {k: sanitize(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [sanitize(v) for v in obj]
    if isinstance(obj, (np.bool_, bool)):
        return bool(obj)
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, np.ndarray):
        return sanitize(obj.tolist())
    if isinstance(obj, (np.floating, float)):
        val = float(obj)
        if math.isnan(val) or math.isinf(val):
            return None
        return val
    return obj


def atomic_write_json(path: str | Path, data: Any, indent: int | None = 2) -> None:
    path = str(path)
    directory = os.path.dirname(path) or '.'
    os.makedirs(directory, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=directory, suffix='.tmp')
    try:
        with os.fdopen(fd, 'w') as f:
            json.dump(data, f, indent=indent)
        os.replace(tmp, path)
    except Exception:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def load_json(path: str | Path, default: Any = None) -> Any:
    try:
        with open(path) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return default


def read_jsonl(path: str | Path) -> list[dict]:
    rows: list[dict] = []
    try:
        with open(path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    except FileNotFoundError:
        return rows
    return rows


def append_jsonl(path: str | Path, row: dict) -> None:
    path = str(path)
    os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
    with open(path, 'a') as f:
        f.write(json.dumps(row) + '\n')
