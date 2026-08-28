import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from quantshield.config import INDIA_MACRO_TICKERS, INDIA_REGIME_WEIGHTS, INDIA_SECTOR_MAP, INDIA_TICKERS, TICKERS
from quantshield.signals import fama_french
from quantshield.signals.composite import SIGNAL_KEYS, composite_score, compute_signals
from quantshield.signals.cross_asset import _market_betas, india_cross_asset_signals, us_cross_asset_signals
from quantshield.signals.fama_french import _parse_monthly, _to_calendar_months, decompose_returns
from quantshield.signals.mean_reversion import rsi_signal
from quantshield.signals.momentum import momentum_signal, vol_adj_momentum
from quantshield.signals.regime import india_detect_regime, us_detect_regime
from quantshield.signals.trend import trend_signal
from quantshield.utils import rank_normalize, sanitize
from tests.conftest import flat_macro, make_dates, make_prices

GOLDEN_PATH = Path(__file__).parent / "fixtures" / "signals_golden.json"
ROWS = 320
DATES = pd.bdate_range(end="2026-08-14", periods=ROWS)


def india_panels(stress: bool) -> tuple[pd.DataFrame, pd.DataFrame]:
    rng = np.random.default_rng(7)
    cols = INDIA_TICKERS + ["NIFTYBEES.NS"]
    base = rng.uniform(150.0, 3500.0, len(cols))
    drift = rng.normal(0.0004, 0.0004, len(cols))
    rets = rng.normal(0.0, 0.016, (ROWS, len(cols))) + drift
    close = pd.DataFrame(base * np.cumprod(1.0 + rets, axis=0), index=DATES, columns=cols)
    t = np.arange(ROWS)
    vix = 13.5 + 1.5 * np.sin(t / 23.0) + rng.normal(0.0, 0.5, ROWS)
    nsei = 23500.0 + 1000.0 * np.sin(t / 45.0) + np.cumsum(rng.normal(0.0, 25.0, ROWS))
    usdinr = 84.0 + 0.6 * np.sin(t / 61.0) + np.cumsum(rng.normal(0.0, 0.03, ROWS))
    oil = 80.0 + 6.0 * np.sin(t / 37.0) + np.cumsum(rng.normal(0.0, 0.25, ROWS))
    if stress:
        vix[-30:] = vix[-30:] + 6.0
        nsei[-70:] = nsei[-70:] * np.linspace(1.0, 0.90, 70)
        usdinr[-21:] = usdinr[-21:] + np.linspace(0.0, 3.8, 21)
        oil[-21:] = oil[-21:] + np.linspace(0.0, 14.0, 21)
    macro = pd.DataFrame({
        "^INDIAVIX": np.clip(vix, 12.0, 25.0 if not stress else 40.0),
        "^NSEI": np.clip(nsei, 22000.0, 25000.0),
        "USDINR=X": np.clip(usdinr, 82.5, 90.0),
        "CL=F": np.clip(oil, 70.0, 95.0 if not stress else 110.0),
    }, index=DATES)
    return close, macro[INDIA_MACRO_TICKERS]


def us_panels(stress: bool) -> tuple[pd.DataFrame, pd.DataFrame, pd.Series]:
    rng = np.random.default_rng(7)
    base = rng.uniform(40.0, 900.0, len(TICKERS))
    rets = rng.normal(0.0004, 0.014, (ROWS, len(TICKERS)))
    close = pd.DataFrame(base * np.cumprod(1.0 + rets, axis=0), index=DATES, columns=TICKERS)
    t = np.arange(ROWS)
    vix = 16.0 + 3.0 * np.sin(t / 19.0) + rng.normal(0.0, 0.7, ROWS)
    tnx = 4.1 + 0.3 * np.sin(t / 53.0) + np.cumsum(rng.normal(0.0, 0.01, ROWS))
    uso = 74.0 + np.cumsum(rng.normal(0.0, 0.3, ROWS))
    gld = 185.0 + np.cumsum(rng.normal(0.02, 0.6, ROWS))
    uup = 27.5 + np.cumsum(rng.normal(0.0, 0.02, ROWS))
    if stress:
        vix[-25:] = vix[-25:] + 12.0
        tnx[-63:] = tnx[-63:] * np.linspace(1.0, 1.08, 63)
        uso[-21:] = uso[-21:] * np.linspace(1.0, 1.07, 21)
    macro = pd.DataFrame({
        "^VIX": np.clip(vix, 10.0, 45.0), "^TNX": tnx, "USO": uso, "GLD": gld, "UUP": uup,
    }, index=DATES)
    bench = pd.Series(100.0 * np.cumprod(1.0 + rng.normal(0.0004, 0.010, ROWS)), index=DATES).pct_change().dropna()
    return close, macro, bench


def rounded(series: pd.Series) -> dict[str, float]:
    return {str(k): (None if pd.isna(v) else round(float(v), 12)) for k, v in series.items()}


@pytest.fixture(scope="module")
def golden() -> dict:
    with open(GOLDEN_PATH) as fh:
        return json.load(fh)


class TestGoldenLivePath:
    @pytest.mark.parametrize("scenario", ["calm", "stress"])
    def test_india_signals_match_golden(self, golden: dict, scenario: str) -> None:
        expected = golden["india"][scenario]
        close, macro = india_panels(scenario == "stress")
        returns = close.pct_change().dropna()
        bench = macro["^NSEI"].pct_change().dropna()

        assert rounded(rank_normalize(momentum_signal(close))) == expected["momentum_rank"]
        assert rounded(vol_adj_momentum(returns)) == expected["vol_adj_momentum"]
        assert rounded(rank_normalize(vol_adj_momentum(returns))) == expected["vol_adj_momentum_rank"]
        assert rounded(rsi_signal(close)) == expected["mean_reversion"]
        assert rounded(trend_signal(close)) == expected["trend"]

        cross, betas = india_cross_asset_signals(close, macro, returns, benchmark_returns=bench, sector_map=INDIA_SECTOR_MAP)
        assert rounded(cross) == expected["cross_asset"]
        assert rounded(rank_normalize(cross)) == expected["cross_asset_rank"]

        old_betas = pd.Series(expected["betas"])
        n = golden["beta_window"]
        assert rank_normalize(betas).round(12).to_dict() == rank_normalize(old_betas).round(12).to_dict()
        np.testing.assert_allclose(betas.reindex(old_betas.index).to_numpy(), old_betas.to_numpy() * (n - 1) / n, rtol=1e-9)

    @pytest.mark.parametrize("scenario", ["calm", "stress"])
    def test_india_regime_matches_golden(self, golden: dict, scenario: str) -> None:
        expected = golden["india"][scenario]["regime"]
        _, macro = india_panels(scenario == "stress")
        regime, confidence, details = india_detect_regime(macro)
        assert regime == expected["detected"]
        assert round(float(confidence), 12) == expected["confidence"]
        clean = sanitize(details)
        assert {k: clean[k] for k in expected["details"]} == expected["details"]
        assert clean["usdinr"] == round(float(macro["USDINR=X"].iloc[-1]), 2)
        assert "vix_percentile" not in clean

    @pytest.mark.parametrize("scenario", ["calm", "stress"])
    def test_india_composite_matches_planner_formula(self, scenario: str) -> None:
        close, macro = india_panels(scenario == "stress")
        returns = close.pct_change().dropna()
        bench = macro["^NSEI"].pct_change().dropna()
        regime, _, _ = india_detect_regime(macro)
        weights = INDIA_REGIME_WEIGHTS[regime]
        signals, _ = compute_signals(close, macro, returns, bench, "india", regime, INDIA_SECTOR_MAP)
        manual = (
            weights["momentum"] * rank_normalize(momentum_signal(close))
            + weights["vol_adj_momentum"] * rank_normalize(vol_adj_momentum(returns))
            + weights["mean_reversion"] * rank_normalize(rsi_signal(close))
            + weights["trend"] * rank_normalize(trend_signal(close))
            + weights["cross_asset"] * rank_normalize(india_cross_asset_signals(
                close, macro, returns, benchmark_returns=bench, sector_map=INDIA_SECTOR_MAP)[0])
        )
        assert composite_score(signals, weights).equals(manual)

    @pytest.mark.parametrize("scenario", ["calm", "stress"])
    def test_us_cross_asset_and_regime_match_golden(self, golden: dict, scenario: str) -> None:
        expected = golden["us"][scenario]
        close, macro, bench = us_panels(scenario == "stress")
        returns = close.pct_change().dropna()
        cross, betas = us_cross_asset_signals(close, macro, returns, benchmark_returns=bench)
        assert rounded(rank_normalize(cross)) == expected["cross_asset_rank"]
        old_betas = pd.Series(expected["betas"])
        n = golden["beta_window"]
        np.testing.assert_allclose(betas.reindex(old_betas.index).to_numpy(), old_betas.to_numpy() * (n - 1) / n, rtol=1e-9)
        regime, confidence, details = us_detect_regime(macro)
        assert regime == expected["regime"]["detected"]
        assert round(float(confidence), 12) == expected["regime"]["confidence"]
        clean = sanitize(details)
        assert {k: clean[k] for k in expected["regime"]["details"]} == expected["regime"]["details"]


class TestMomentum:
    def test_raw_output_ranks_identically_to_ranked_output(self) -> None:
        raw = pd.Series([0.31, -0.2, 0.31, 0.05, np.nan, 1.7, -0.9], index=list("ABCDEFG"))
        legacy = raw.rank(pct=True) * 2 - 1
        assert rank_normalize(raw).equals(rank_normalize(legacy))

    def test_short_history_returns_float_zeros(self) -> None:
        dates = make_dates(100)
        prices = pd.DataFrame({"A": np.linspace(10, 20, 100), "B": np.linspace(20, 10, 100)}, index=dates)
        out = momentum_signal(prices)
        assert out.dtype == float
        assert (out == 0.0).all()
        vout = vol_adj_momentum(prices.pct_change().dropna())
        assert vout.dtype == float
        assert (vout == 0.0).all()

    def test_momentum_is_return_over_skip_window(self, prices: pd.DataFrame) -> None:
        out = momentum_signal(prices, lookback=252, skip=21)
        window = prices.iloc[-273:-21]
        expected = window.iloc[-1] / window.iloc[0] - 1
        assert out.equals(expected)

    def test_vol_adj_zero_vol_gets_neutral_score(self) -> None:
        dates = pd.bdate_range(end="2025-01-15", periods=300)
        rng = np.random.default_rng(1)
        returns = pd.DataFrame({"FLAT": np.zeros(300), "A": rng.normal(0.001, 0.02, 300), "B": rng.normal(0, 0.02, 300)}, index=dates)
        out = vol_adj_momentum(returns)
        assert out["FLAT"] == 0.0
        assert out.between(-1, 1).all()


class TestTrend:
    def test_short_history_returns_zeros_not_minus_one(self) -> None:
        dates = pd.bdate_range(end="2025-01-15", periods=199)
        prices = pd.DataFrame({"UP": np.linspace(50, 150, 199), "DN": np.linspace(150, 50, 199)}, index=dates)
        out = trend_signal(prices)
        assert (out == 0.0).all()
        assert out.dtype == float

    def test_exactly_200_rows_scores(self) -> None:
        dates = pd.bdate_range(end="2025-01-15", periods=200)
        prices = pd.DataFrame({"UP": np.linspace(50, 150, 200), "DN": np.linspace(150, 50, 200)}, index=dates)
        out = trend_signal(prices)
        assert out["UP"] == 1.0
        assert out["DN"] == -1.0

    def test_components_sum_to_known_grid(self, prices: pd.DataFrame) -> None:
        out = trend_signal(prices)
        allowed = {round(s * 2 - 1, 10) for s in (0.0, 0.2, 0.3, 0.5, 0.7, 0.8, 1.0)}
        assert set(out.round(10)) <= allowed


class TestRsi:
    def test_monotone_moves_saturate(self) -> None:
        dates = pd.bdate_range(end="2025-01-15", periods=60)
        prices = pd.DataFrame({"UP": np.linspace(50, 200, 60), "DN": np.linspace(200, 50, 60)}, index=dates)
        out = rsi_signal(prices)
        assert out["UP"] == pytest.approx(-1.0)
        assert out["DN"] == pytest.approx(1.0)

    def test_hand_computed_rsi(self) -> None:
        dates = pd.bdate_range(end="2025-01-15", periods=15)
        moves = np.array([0.01, -0.02, 0.03, 0.01, -0.01, 0.02, -0.03, 0.01, 0.02, -0.01, 0.01, 0.01, -0.02, 0.03])
        prices = pd.DataFrame({"X": 100 * np.cumprod(np.concatenate([[1.0], 1 + moves]))}, index=dates)
        ret = prices["X"].pct_change().iloc[1:]
        rs = ret.clip(lower=0).mean() / (-ret.clip(upper=0)).mean()
        expected = (50 - (100 - 100 / (1 + rs))) / 50
        assert rsi_signal(prices)["X"] == pytest.approx(expected)


class TestRegimeThresholds:
    @pytest.mark.parametrize("vix,expected,scores", [
        (10.0, "risk_on", {"risk_on": 4, "risk_off": 0, "crisis": 0}),
        (17.0, "risk_on", {"risk_on": 3, "risk_off": 0, "crisis": 0}),
        (22.0, "risk_off", {"risk_on": 1, "risk_off": 2, "crisis": 0}),
        (27.0, "risk_off", {"risk_on": 1, "risk_off": 2, "crisis": 1}),
        (32.0, "crisis", {"risk_on": 1, "risk_off": 1, "crisis": 2}),
        (40.0, "crisis", {"risk_on": 1, "risk_off": 0, "crisis": 3}),
    ])
    def test_us_vix_buckets(self, dates_300: pd.DatetimeIndex, vix: float, expected: str, scores: dict) -> None:
        regime, confidence, details = us_detect_regime(flat_macro(dates_300, **{"^VIX": vix}))
        assert regime == expected
        assert details["regime_scores"] == scores
        assert details["vix_trend"] == "falling"
        assert confidence == pytest.approx(scores[expected] / sum(scores.values()))

    @pytest.mark.parametrize("vix,expected,scores", [
        (12.0, "risk_on", {"risk_on": 4, "risk_off": 0, "crisis": 0}),
        (18.0, "risk_off", {"risk_on": 1, "risk_off": 2, "crisis": 0}),
        (25.0, "crisis", {"risk_on": 1, "risk_off": 0, "crisis": 3}),
    ])
    def test_india_vix_buckets(self, dates_300: pd.DatetimeIndex, vix: float, expected: str, scores: dict) -> None:
        regime, _, details = india_detect_regime(flat_macro(dates_300, **{"^INDIAVIX": vix}))
        assert regime == expected
        assert details["regime_scores"] == scores

    def test_vix_trend_votes(self, dates_300: pd.DatetimeIndex) -> None:
        base = np.full(300, 15.0)
        fast = base.copy()
        fast[-1] = 19.0
        rising = base.copy()
        rising[-1] = 16.0
        _, _, d_fast = us_detect_regime(pd.DataFrame({"^VIX": fast}, index=dates_300))
        _, _, d_rising = us_detect_regime(pd.DataFrame({"^VIX": rising}, index=dates_300))
        assert d_fast["vix_trend"] == "rising_fast" and d_fast["regime_scores"]["crisis"] == 1
        assert d_rising["vix_trend"] == "rising" and d_rising["regime_scores"]["risk_off"] == 1

    def test_short_vix_history_skips_trend_vote(self) -> None:
        dates = pd.bdate_range(end="2025-01-15", periods=30)
        _, _, details = us_detect_regime(flat_macro(dates, **{"^VIX": 12.0}))
        assert details["vix_trend"] == "unavailable"
        assert details["vix_sma50"] is None
        assert details["regime_scores"] == {"risk_on": 3, "risk_off": 0, "crisis": 0}

    def test_missing_vix_column(self, dates_300: pd.DatetimeIndex) -> None:
        regime, confidence, details = us_detect_regime(flat_macro(dates_300, GLD=180.0))
        assert details["vix_current"] is None
        assert details["vix_trend"] == "unavailable"
        assert regime == "risk_on" and confidence == 1.0

    def test_empty_macro_defaults_to_risk_on_zero_confidence(self, dates_300: pd.DatetimeIndex) -> None:
        regime, confidence, details = india_detect_regime(pd.DataFrame(index=dates_300))
        assert regime == "risk_on"
        assert confidence == 0.0
        assert details["regime_probs"] == {"risk_on": 0.0, "risk_off": 0.0, "crisis": 0.0}

    def test_india_usdinr_level_and_votes(self, dates_300: pd.DatetimeIndex) -> None:
        usdinr = np.full(300, 84.0)
        usdinr[-1] = 84.0 * 1.045
        _, _, details = india_detect_regime(pd.DataFrame({"USDINR=X": usdinr}, index=dates_300))
        assert details["usdinr"] == round(84.0 * 1.045, 2)
        assert details["rupee_1m_change"] == pytest.approx(4.5)
        assert details["regime_scores"]["crisis"] == 1

    def test_india_nifty_vs_sma50(self, dates_300: pd.DatetimeIndex) -> None:
        up = pd.DataFrame({"^NSEI": np.linspace(22000, 25000, 300)}, index=dates_300)
        down = pd.DataFrame({"^NSEI": np.linspace(25000, 22000, 300)}, index=dates_300)
        assert india_detect_regime(up)[2]["regime_scores"]["risk_on"] == 1
        assert india_detect_regime(down)[2]["regime_scores"]["risk_off"] == 1

    def test_tie_breaks_toward_earlier_regime_key(self, dates_300: pd.DatetimeIndex) -> None:
        macro = flat_macro(dates_300, **{"^INDIAVIX": 18.0})
        macro["^NSEI"] = np.linspace(22000, 25000, 300)
        regime, confidence, details = india_detect_regime(macro)
        assert details["regime_scores"] == {"risk_on": 2, "risk_off": 2, "crisis": 0}
        assert regime == "risk_on"
        assert confidence == 0.5
        assert "oil_override" not in details


class TestIndiaRegimeOil:
    def make_india_macro(self, oil: np.ndarray) -> pd.DataFrame:
        dates = pd.bdate_range(end="2026-07-17", periods=260)
        n = len(dates)
        return pd.DataFrame({
            "^INDIAVIX": np.full(n, 12.0),
            "^NSEI": np.linspace(22000, 26000, n),
            "USDINR=X": np.full(n, 84.0),
            "CL=F": oil,
        }, index=dates)

    def test_baseline_risk_on_with_calm_oil(self) -> None:
        regime, confidence, details = india_detect_regime(self.make_india_macro(np.full(260, 75.0)))
        assert regime == "risk_on"
        assert "oil_override" not in details

    def test_oil_above_90_blocks_risk_on(self) -> None:
        regime, confidence, details = india_detect_regime(self.make_india_macro(np.full(260, 95.0)))
        assert regime == "risk_off"
        assert "oil_override" in details
        assert details["oil_level"] == 95.0
        assert details["regime_scores"]["risk_off"] >= 1
        assert confidence == details["regime_scores"]["risk_off"] / sum(details["regime_scores"].values())

    def test_oil_spike_crisis_vote_gated_on_level(self) -> None:
        oil = np.full(260, 70.0)
        oil[-15:] = 85.0
        _, _, details = india_detect_regime(self.make_india_macro(oil))
        assert details["oil_1m_return"] > 15
        assert details["oil_level"] == 85.0
        assert details["regime_scores"]["crisis"] == 2
        oil_high = np.full(260, 78.0)
        oil_high[-15:] = 95.0
        _, _, details_high = india_detect_regime(self.make_india_macro(oil_high))
        assert details_high["oil_1m_return"] > 15
        assert details_high["oil_level"] == 95.0
        assert details_high["regime_scores"]["crisis"] == 3
        oil_mild = np.full(260, 70.0)
        oil_mild[-15:] = 78.0
        _, _, details_mild = india_detect_regime(self.make_india_macro(oil_mild))
        assert 10 < details_mild["oil_1m_return"] <= 15
        assert details_mild["regime_scores"]["crisis"] == 2


class TestMarketBetas:
    def test_matches_ols_slope(self, returns: pd.DataFrame, benchmark_returns: pd.Series) -> None:
        betas = _market_betas(returns, benchmark_returns, window=126)
        common = returns.index.intersection(benchmark_returns.index)
        x = benchmark_returns.loc[common].iloc[-126:].to_numpy()
        for col in returns.columns:
            y = returns.loc[common, col].iloc[-126:].to_numpy()
            slope = np.polyfit(x, y, 1)[0]
            assert betas[col] == pytest.approx(slope, rel=1e-9)

    def test_fallback_without_benchmark(self, returns: pd.DataFrame) -> None:
        assert (_market_betas(returns, None) == 1.0).all()
        assert (_market_betas(returns, returns.iloc[-50:, 0]) == 1.0).all()

    def test_fallback_on_constant_benchmark(self, returns: pd.DataFrame) -> None:
        flat = pd.Series(0.0, index=returns.index)
        assert (_market_betas(returns, flat) == 1.0).all()

    def test_benchmark_beta_is_one(self, returns: pd.DataFrame) -> None:
        bench = returns["AAPL"]
        assert _market_betas(returns, bench)["AAPL"] == pytest.approx(1.0)


class TestUsCrossAsset:
    def test_no_gate_returns_zeros_and_betas(self, prices: pd.DataFrame, returns: pd.DataFrame, benchmark_returns: pd.Series, dates_300: pd.DatetimeIndex) -> None:
        macro = flat_macro(dates_300, **{"^VIX": 15.0, "^TNX": 4.0, "USO": 70.0})
        signal, betas = us_cross_asset_signals(prices, macro, returns, benchmark_returns=benchmark_returns)
        assert (signal == 0.0).all()
        assert betas.equals(_market_betas(returns, benchmark_returns))

    @pytest.mark.parametrize("trigger", ["vix", "yield", "oil"])
    def test_each_gate_ranks_negative_beta(self, trigger: str, prices: pd.DataFrame, returns: pd.DataFrame, benchmark_returns: pd.Series, dates_300: pd.DatetimeIndex) -> None:
        macro = flat_macro(dates_300, **{"^VIX": 15.0, "^TNX": 4.0, "USO": 70.0})
        if trigger == "vix":
            macro.loc[macro.index[-1], "^VIX"] = 18.5
        elif trigger == "yield":
            macro.loc[macro.index[-1], "^TNX"] = 4.0 * 1.06
        else:
            macro.loc[macro.index[-1], "USO"] = 70.0 * 1.06
        signal, betas = us_cross_asset_signals(prices, macro, returns, benchmark_returns=benchmark_returns)
        assert signal.equals(rank_normalize(-betas))
        assert signal.idxmax() == betas.idxmin()

    def test_gate_without_benchmark_is_flat(self, prices: pd.DataFrame, returns: pd.DataFrame, dates_300: pd.DatetimeIndex) -> None:
        macro = flat_macro(dates_300, **{"^VIX": 30.0})
        signal, betas = us_cross_asset_signals(prices, macro, returns)
        assert (betas == 1.0).all()
        assert (signal == 0.0).all()


class TestIndiaCrossAsset:
    def make_macro(self, dates: pd.DatetimeIndex, usdinr_last: float = 84.0, oil_last: float = 80.0, nifty_last: float = 24000.0) -> pd.DataFrame:
        macro = flat_macro(dates, **{"^INDIAVIX": 13.0, "^NSEI": 24000.0, "USDINR=X": 84.0, "CL=F": 80.0})
        macro.loc[macro.index[-1], "USDINR=X"] = usdinr_last
        macro.loc[macro.index[-1], "CL=F"] = oil_last
        macro.loc[macro.index[-1], "^NSEI"] = nifty_last
        return macro

    def india_close(self, dates: pd.DatetimeIndex) -> pd.DataFrame:
        return make_prices(len(dates), tuple(INDIA_TICKERS), seed=5, drift=0.0003, vol=0.015).set_axis(dates)

    def test_rupee_depreciation_favours_it_hurts_consumer(self, dates_300: pd.DatetimeIndex) -> None:
        close = self.india_close(dates_300)
        macro = self.make_macro(dates_300, usdinr_last=84.0 * 1.02)
        signal, _ = india_cross_asset_signals(close, macro, close.pct_change().dropna(), sector_map=INDIA_SECTOR_MAP)
        assert (signal[INDIA_SECTOR_MAP["it_exporters"]] > 0).all()
        assert (signal[INDIA_SECTOR_MAP["consumer"]] < 0).all()
        others = [t for t in INDIA_TICKERS if t not in INDIA_SECTOR_MAP["it_exporters"] + INDIA_SECTOR_MAP["consumer"]]
        assert (signal[others] == 0.0).all()
        assert signal.abs().max() == pytest.approx(1.0, abs=1e-6)

    def test_oil_spike_hits_consumer_hardest(self, dates_300: pd.DatetimeIndex) -> None:
        close = self.india_close(dates_300)
        macro = self.make_macro(dates_300, oil_last=80.0 * 1.10)
        signal, _ = india_cross_asset_signals(close, macro, close.pct_change().dropna(), sector_map=INDIA_SECTOR_MAP)
        assert (signal < 0).all()
        assert signal[INDIA_SECTOR_MAP["consumer"]].max() < signal.drop(INDIA_SECTOR_MAP["consumer"]).min()

    def test_nifty_drawdown_penalises_banks(self, dates_300: pd.DatetimeIndex) -> None:
        close = self.india_close(dates_300)
        macro = self.make_macro(dates_300, nifty_last=24000.0 * 0.93)
        signal, _ = india_cross_asset_signals(close, macro, close.pct_change().dropna(), sector_map=INDIA_SECTOR_MAP)
        assert signal[INDIA_SECTOR_MAP["banks"]].to_numpy() == pytest.approx(-1.0, abs=1e-6)
        assert (signal.drop(INDIA_SECTOR_MAP["banks"]) == 0.0).all()

    def test_no_sector_map_keeps_only_broad_oil_impact(self, dates_300: pd.DatetimeIndex) -> None:
        close = self.india_close(dates_300)
        macro = self.make_macro(dates_300, usdinr_last=86.0, oil_last=95.0, nifty_last=22000.0)
        signal, betas = india_cross_asset_signals(close, macro, close.pct_change().dropna())
        assert (signal < 0).all()
        assert signal.max() - signal.min() < 1e-12
        assert (rank_normalize(signal) == 0.0).all()
        assert (betas == 1.0).all()

    def test_short_macro_history_is_neutral(self) -> None:
        dates = pd.bdate_range(end="2025-01-15", periods=15)
        close = self.india_close(dates)
        macro = self.make_macro(dates, usdinr_last=90.0, oil_last=100.0)
        signal, _ = india_cross_asset_signals(close, macro, close.pct_change().dropna(), sector_map=INDIA_SECTOR_MAP)
        assert (signal == 0.0).all()


class TestComposite:
    def test_compute_signals_keys_and_ranges(self, prices: pd.DataFrame, returns: pd.DataFrame, benchmark_returns: pd.Series, dates_300: pd.DatetimeIndex) -> None:
        macro = flat_macro(dates_300, **{"^VIX": 22.0, "^TNX": 4.0, "USO": 70.0})
        signals, betas = compute_signals(prices, macro, returns, benchmark_returns, "us", "risk_off", None)
        assert list(signals) == SIGNAL_KEYS
        for key, series in signals.items():
            assert series.index.equals(prices.columns), key
            assert series.between(-1, 1).all(), key
            assert series.notna().all(), key
        assert betas.index.equals(returns.columns)

    def test_unknown_market_raises(self, prices: pd.DataFrame, returns: pd.DataFrame, dates_300: pd.DatetimeIndex) -> None:
        with pytest.raises(ValueError):
            compute_signals(prices, flat_macro(dates_300), returns, None, "uk", "risk_on", None)

    def test_composite_score_ignores_unknown_weights(self, prices: pd.DataFrame, returns: pd.DataFrame, dates_300: pd.DatetimeIndex) -> None:
        signals, _ = compute_signals(prices, flat_macro(dates_300), returns, None, "us", "risk_on", None)
        weights = {"momentum": 0.6, "trend": 0.4, "earnings": 0.9}
        expected = 0.6 * signals["momentum"] + 0.4 * signals["trend"]
        assert composite_score(signals, weights).equals(expected)

    def test_composite_score_empty_signals_raises(self) -> None:
        with pytest.raises(ValueError):
            composite_score({}, {"momentum": 1.0})

    def test_zero_weights_give_zero_series(self, prices: pd.DataFrame, returns: pd.DataFrame, dates_300: pd.DatetimeIndex) -> None:
        signals, _ = compute_signals(prices, flat_macro(dates_300), returns, None, "us", "risk_on", None)
        out = composite_score(signals, {k: 0.0 for k in SIGNAL_KEYS})
        assert (out == 0.0).all()
        assert out.index.equals(prices.columns)


FF5_SAMPLE = "\n".join([
    "This file was created using the 202606 CRSP database.",
    "",
    ",Mkt-RF,SMB,HML,RMW,CMA,RF",
    "202401,    1.50,   -0.20,    0.30,    0.10,   -0.05,    0.40",
    "202402,   -0.75,    0.60,  -99.99,    0.20,    0.15,    0.41",
    "",
    " Annual Factors: January-December ",
    ",Mkt-RF,SMB,HML,RMW,CMA,RF",
    "  2024,   12.00,    1.00,    2.00,    3.00,    4.00,    5.00",
])


class TestFamaFrench:
    def test_parse_monthly_block_only(self) -> None:
        frame = _parse_monthly(FF5_SAMPLE)
        assert list(frame.columns) == ["Mkt-RF", "SMB", "HML", "RMW", "CMA", "RF"]
        assert list(frame.index) == [pd.Timestamp("2024-01-01"), pd.Timestamp("2024-02-01")]
        assert frame.loc["2024-01-01", "Mkt-RF"] == pytest.approx(0.015)
        assert np.isnan(frame.loc["2024-02-01", "HML"])
        assert frame.loc["2024-02-01", "RF"] == pytest.approx(0.0041)

    def test_insufficient_data(self) -> None:
        idx = pd.date_range("2024-01-31", periods=5, freq="ME")
        out = decompose_returns(pd.Series(0.01, index=idx))
        assert out == {"error": "insufficient_data", "n_months": 5}

    def test_factor_data_unavailable(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(fama_french, "get_factor_data", lambda s, e: None)
        idx = pd.date_range("2022-01-31", periods=24, freq="ME")
        out = decompose_returns(pd.Series(0.01, index=idx))
        assert out == {"error": "factor_data_unavailable", "n_months": 24}

    def test_insufficient_overlap(self, monkeypatch: pytest.MonkeyPatch) -> None:
        factors = pd.DataFrame(
            {c: 0.01 for c in ["Mkt-RF", "SMB", "HML", "RMW", "CMA", "Mom", "RF"]},
            index=pd.date_range("2010-01-01", periods=24, freq="MS"),
        )
        monkeypatch.setattr(fama_french, "get_factor_data", lambda s, e: factors)
        idx = pd.date_range("2022-01-31", periods=24, freq="ME")
        out = decompose_returns(pd.Series(0.01, index=idx))
        assert out == {"error": "insufficient_overlap", "n_months": 0}

    def test_recovers_planted_loadings(self, monkeypatch: pytest.MonkeyPatch) -> None:
        rng = np.random.default_rng(11)
        idx = pd.date_range("2018-01-01", periods=72, freq="MS")
        factors = pd.DataFrame({
            "Mkt-RF": rng.normal(0.006, 0.04, 72), "SMB": rng.normal(0.0, 0.02, 72), "HML": rng.normal(0.0, 0.02, 72),
            "RMW": rng.normal(0.0, 0.015, 72), "CMA": rng.normal(0.0, 0.015, 72), "Mom": rng.normal(0.0, 0.03, 72),
            "RF": np.full(72, 0.002),
        }, index=idx)
        monkeypatch.setattr(fama_french, "get_factor_data", lambda s, e: factors)
        port = 0.002 + factors["RF"] + 1.2 * factors["Mkt-RF"] - 0.4 * factors["HML"] + rng.normal(0, 0.002, 72)
        port.index = idx + pd.offsets.MonthEnd(0)
        out = decompose_returns(port)
        assert "error" not in out
        assert out["n_months"] == 72
        assert out["factors_used"] == ["Mkt-RF", "SMB", "HML", "RMW", "CMA", "Mom"]
        assert out["factor_betas"]["Mkt-RF"]["beta"] == pytest.approx(1.2, abs=0.03)
        assert out["factor_betas"]["HML"]["beta"] == pytest.approx(-0.4, abs=0.05)
        assert out["alpha"] == pytest.approx(0.002, abs=0.001)
        assert out["residual_alpha_annualized"] == pytest.approx(out["alpha"] * 12, abs=1e-4)
        assert out["newey_west_lags"] == 4
        assert 0.9 < out["r_squared"] <= 1.0

    def test_returns_in_same_month_are_compounded(self) -> None:
        idx = pd.DatetimeIndex(["2020-01-02", "2020-01-31", "2020-02-28", "2020-03-31"])
        port = pd.Series([0.10, 0.05, np.nan, -0.02], index=idx)
        out = _to_calendar_months(port)
        assert list(out.index) == [pd.Timestamp("2020-01-01"), pd.Timestamp("2020-03-01")]
        assert out.iloc[0] == pytest.approx(1.10 * 1.05 - 1)
        assert out.iloc[1] == pytest.approx(-0.02)
