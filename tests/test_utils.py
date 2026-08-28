import json
import os
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from quantshield.utils import append_jsonl, atomic_write_json, load_json, rank_normalize, read_jsonl, sanitize


class Unserialisable:
    pass


class TestAtomicWriteJson:
    def test_writes_json_and_leaves_no_temp_file(self, tmp_path: Path) -> None:
        target = tmp_path / 'nested' / 'out.json'
        atomic_write_json(target, {'a': 1, 'b': [1.5, None]})
        assert json.loads(target.read_text()) == {'a': 1, 'b': [1.5, None]}
        assert sorted(os.listdir(tmp_path / 'nested')) == ['out.json']

    def test_indent_none_writes_single_line(self, tmp_path: Path) -> None:
        target = tmp_path / 'compact.json'
        atomic_write_json(target, {'a': {'b': [1, 2]}}, indent=None)
        assert target.read_text() == '{"a": {"b": [1, 2]}}'

    def test_failing_dump_keeps_previous_file_and_removes_temp(self, tmp_path: Path) -> None:
        target = tmp_path / 'state.json'
        atomic_write_json(target, {'holdings': {'X': 1}})
        before = target.read_bytes()
        with pytest.raises(TypeError):
            atomic_write_json(target, {'holdings': {'X': 1}, 'bad': Unserialisable()})
        assert target.read_bytes() == before
        assert sorted(os.listdir(tmp_path)) == ['state.json']

    def test_failing_dump_on_fresh_path_creates_nothing(self, tmp_path: Path) -> None:
        target = tmp_path / 'fresh' / 'state.json'
        with pytest.raises(TypeError):
            atomic_write_json(target, [Unserialisable()])
        assert not target.exists()
        assert os.listdir(tmp_path / 'fresh') == []

    def test_overwrite_replaces_content_atomically(self, tmp_path: Path) -> None:
        target = tmp_path / 'x.json'
        atomic_write_json(target, list(range(1000)))
        atomic_write_json(target, [1])
        assert json.loads(target.read_text()) == [1]
        assert [p for p in os.listdir(tmp_path) if p.endswith('.tmp')] == []


class TestJsonHelpers:
    def test_load_json_default_on_missing_or_corrupt(self, tmp_path: Path) -> None:
        assert load_json(tmp_path / 'missing.json') is None
        assert load_json(tmp_path / 'missing.json', default=[]) == []
        bad = tmp_path / 'bad.json'
        bad.write_text('{not json')
        assert load_json(bad, default={'d': 1}) == {'d': 1}

    def test_jsonl_roundtrip_skips_blank_and_corrupt_lines(self, tmp_path: Path) -> None:
        path = tmp_path / 'rows.jsonl'
        append_jsonl(path, {'a': 1})
        append_jsonl(path, {'b': 2})
        with open(path, 'a') as f:
            f.write('\n{broken\n')
        assert read_jsonl(path) == [{'a': 1}, {'b': 2}]
        assert read_jsonl(tmp_path / 'absent.jsonl') == []


class TestSanitize:
    @pytest.mark.parametrize('value', [np.float64(np.nan), np.float64(np.inf), np.float64(-np.inf), float('nan'), float('inf')])
    def test_non_finite_becomes_none(self, value: float) -> None:
        assert sanitize({'v': value})['v'] is None

    def test_numpy_scalars_become_python_types(self) -> None:
        out = sanitize({'b': np.bool_(True), 'i': np.int64(42), 'f': np.float64(3.14), 'a': np.array([1, 2, 3])})
        assert out == {'b': True, 'i': 42, 'f': 3.14, 'a': [1, 2, 3]}
        assert type(out['b']) is bool and type(out['i']) is int and type(out['f']) is float

    def test_nested_roundtrip(self) -> None:
        data = {'a': {'b': np.float64(np.nan), 'c': [np.int64(1), np.inf]}, 'z': (np.bool_(False), 1.5)}
        parsed = json.loads(json.dumps(sanitize(data)))
        assert parsed == {'a': {'b': None, 'c': [1, None]}, 'z': [False, 1.5]}

    @given(
        val=st.one_of(
            st.integers(min_value=-1000, max_value=1000),
            st.floats(allow_nan=True, allow_infinity=True),
            st.booleans(),
        )
    )
    @settings(max_examples=50, deadline=2000)
    def test_handles_all_numpy_scalar_types(self, val: object) -> None:
        if isinstance(val, bool):
            np_val = np.bool_(val)
        elif isinstance(val, int):
            np_val = np.int64(val)
        else:
            np_val = np.float64(val)
        result = sanitize({'v': np_val})
        parsed = json.loads(json.dumps(result))
        if isinstance(val, float) and not np.isfinite(val):
            assert parsed['v'] is None
        else:
            assert parsed['v'] == val


class TestRankNormalizeProperties:
    @given(values=st.lists(st.floats(min_value=-10, max_value=10, allow_nan=False), min_size=2, max_size=12))
    @settings(max_examples=50, deadline=2000)
    def test_idempotent_on_ranked_input(self, values: list) -> None:
        raw = pd.Series(values, index=[f'T{i}' for i in range(len(values))])
        legacy = raw.rank(pct=True) * 2 - 1
        assert rank_normalize(raw).equals(rank_normalize(legacy))
