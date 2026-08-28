import json

import numpy as np
import pandas as pd
import pytest

from quantshield.risk.drawdown import compute_drawdown_status
from quantshield.utils import sanitize
from tests.conftest import make_dates, make_returns


def _single_asset(path: list[float]) -> tuple[pd.DataFrame, pd.Series]:
    return pd.DataFrame({"A": path}, index=make_dates(len(path))), pd.Series({"A": 1.0})


class TestDrawdownStatus:
    def test_output_keys(self):
        returns = make_returns(300, ("A", "B", "C"), seed=42)
        result = compute_drawdown_status(returns, pd.Series(1.0 / 3, index=returns.columns), days=100)
        assert set(result) == {'static_weight_drawdown_pct', 'max_historical_drawdown_pct', 'status'}
        assert 'current_drawdown_pct' not in result
        assert result['status'] in ('NORMAL', 'CAUTION', 'CRITICAL')
        assert result['max_historical_drawdown_pct'] <= result['static_weight_drawdown_pct'] <= 0

    def test_hand_computed_path(self):
        returns, weights = _single_asset([0.10, 0.10, -0.20, 0.05])
        result = compute_drawdown_status(returns, weights, days=4)
        peak = 1.1 * 1.1
        trough = peak * 0.8
        current = trough * 1.05
        assert result['static_weight_drawdown_pct'] == pytest.approx(round((current - peak) / peak * 100, 2), abs=1e-9)
        assert result['max_historical_drawdown_pct'] == pytest.approx(-20.0, abs=1e-9)
        assert result['status'] == 'NORMAL'

    def test_caution_threshold(self):
        returns, weights = _single_asset([0.0] * 10 + [-0.35])
        result = compute_drawdown_status(returns, weights, days=11)
        assert result['static_weight_drawdown_pct'] == pytest.approx(-35.0)
        assert result['status'] == 'CAUTION'

    def test_critical_threshold(self):
        returns, weights = _single_asset([0.0] * 10 + [-0.55])
        result = compute_drawdown_status(returns, weights, max_drawdown_tolerance=0.50, days=11)
        assert result['static_weight_drawdown_pct'] == pytest.approx(-55.0)
        assert result['status'] == 'CRITICAL'

    def test_tolerance_is_respected(self):
        returns, weights = _single_asset([0.0] * 10 + [-0.55])
        assert compute_drawdown_status(returns, weights, max_drawdown_tolerance=0.60, days=11)['status'] == 'CAUTION'

    def test_recovered_path_is_normal(self):
        returns, weights = _single_asset([-0.40, 0.90])
        result = compute_drawdown_status(returns, weights, days=2)
        assert result['static_weight_drawdown_pct'] == 0.0
        assert result['max_historical_drawdown_pct'] == pytest.approx(-40.0)
        assert result['status'] == 'NORMAL'

    def test_days_window_is_applied(self):
        returns, weights = _single_asset([-0.55] + [0.0] * 20)
        assert compute_drawdown_status(returns, weights, days=21)['status'] == 'CRITICAL'
        assert compute_drawdown_status(returns, weights, days=20)['status'] == 'NORMAL'

    def test_zero_returns_normal(self):
        returns = pd.DataFrame({"A": np.zeros(100), "B": np.zeros(100)}, index=make_dates(100))
        result = compute_drawdown_status(returns, pd.Series({"A": 0.5, "B": 0.5}), days=100)
        assert result['status'] == 'NORMAL'
        assert result['static_weight_drawdown_pct'] == 0.0
        assert result['max_historical_drawdown_pct'] == 0.0

    def test_json_serializable(self):
        returns, weights = _single_asset([0.01, -0.02, 0.03])
        parsed = json.loads(json.dumps(sanitize(compute_drawdown_status(returns, weights, days=3))))
        assert parsed['status'] == 'NORMAL'

    def test_redirect_contributions_removed(self):
        import quantshield.risk.drawdown as module
        assert not hasattr(module, 'redirect_contributions')
