# Walk-Forward Validation: Copper/Gold Ratio

**Date:** 2026-04-01
**Purpose:** Walk-forward validation required before engine integration

## Protocol

- **Training window:** 12 months (252 trading days)
- **Test window:** 1 month (21 trading days)
- **Roll:** forward by 1 month
- **Signal:** Inverted 21-day Cu/Au momentum (as recommended in 2026-04-01_copper_gold_ratio.md)
- **Transaction costs:** 15bps per side
- **Data:** 2019-01-02 to 2026-03-31, 1,779 usable observations
- **Walk-forward periods:** 72 (2020-02-03 to 2026-02-06)

At each step, the signal is computed using ONLY training data parameters (sign, normalization). The inverted sign (falling Cu/Au = bullish) is held constant throughout, as this was the pre-registered hypothesis from the static study.

## Walk-Forward IC Results

| Metric | Value |
|-|-|
| Mean WF IC | **0.1554** |
| Std WF IC | 0.4377 |
| WF ICIR | **0.3552** |
| % periods IC > 0 | **66.7%** |
| % periods p < 0.05 | 47.2% |
| T-test on WF ICs | t=3.01, **p=0.0036** |

The walk-forward ICIR of 0.35 is positive and significant. Two-thirds of monthly test periods have positive IC, confirming the inverted signal direction is persistent.

## Walk-Forward L/S Returns (15bps costs)

| Metric | Value |
|-|-|
| L/S return per period (gross) | **1.54%** |
| L/S return per period (net) | **1.24%** |
| Annualized Sharpe (gross) | **1.218** |
| Annualized Sharpe (net) | **0.981** |
| Cumulative L/S return (72 periods) | **182.4%** |
| Annualized L/S return | **18.9%** |

The signal generates meaningful alpha even after 15bps per-side costs. Annualized Sharpe near 1.0 net of costs is strong for a single cross-asset signal.

## Regime Dependency (Walk-Forward)

| Regime | n | Mean IC | ICIR | L/S per period |
|-|-|-|-|-|
| risk_on (VIX < 15) | 9 | -0.0750 | -0.18 | -0.52% |
| risk_off (15 <= VIX < 25) | 47 | 0.1086 | 0.25 | 0.90% |
| crisis (VIX >= 25) | 16 | **0.4227** | **1.29** | **4.61%** |

**Critical regime finding confirmed in walk-forward:**
- The inverted Cu/Au signal works STRONGLY in crisis periods (ICIR 1.29, L/S 4.61%/month)
- Works moderately in normal risk-off periods (ICIR 0.25)
- Fails in calm/risk-on periods (negative IC)
- This is consistent with the static finding that the signal flips in low-VIX regimes

**Implication for engine:** Implement as regime-conditional signal. Apply only when VIX >= 15 (risk_off or crisis). Zero weight in risk_on regime.

## Sign Persistence

| Test | IC | p-value |
|-|-|-|
| Full WF pooled sample | 0.0820 | 0.0014 |
| First half WF periods (periods 1-36) | 0.1919 | n/a |
| Second half WF periods (periods 37-72) | 0.1190 | n/a |

The inverted sign (falling Cu/Au = bullish) persists across both halves of the walk-forward. The first half is stronger (0.19 vs 0.12), showing some decay but NO sign flip. The signal direction is stable.

## Comparison: Static IS/OOS vs Walk-Forward

| Method | IC | Notes |
|-|-|-|
| Static IS (70%) | 0.0363 (p=0.20) | Weak, not significant |
| Static OOS (30%) | 0.1204 (p=0.005) | Strong, significant |
| Walk-Forward | 0.1554 (p=0.004) | Strongest, significant |

Walk-forward IC (0.155) is STRONGER than both static IS (0.036) and OOS (0.120). This is unusual and suggests the signal benefits from the adaptive training window, the rolling 12-month calibration captures regime-specific dynamics better than a fixed IS/OOS split.

## Dollar-Orthogonalization

| Signal | Full-Sample IC | WF ICIR |
|-|-|-|
| Raw Cu/Au (inverted) | 0.0556 (p=0.019) | **0.355** |
| DXY-orthogonalized Cu/Au (inverted) | 0.0550 (p=0.020) | 0.180 |
| IC retained after orthogonalization | **98.9%** | 50.7% |

**Key finding:** The full-sample IC is almost perfectly retained (98.9%) after regressing out UUP/dollar momentum. The Cu/Au signal is NOT a dollar proxy, it carries independent information.

However, the walk-forward ICIR drops from 0.355 to 0.180 after orthogonalization. This suggests that while the signal's average IC is dollar-independent, the period-by-period consistency benefits from dollar alignment. The orthogonalized version is noisier month-to-month but retains the correct sign.

**Recommendation:** Use raw Cu/Au momentum (not orthogonalized). The dollar component adds stability without introducing redundancy, since UUP is used differently in the current cross-asset module (level-based, not momentum-based).

## Walk-Forward Quintile Analysis

| Quintile | n | Mean 21d Return | Std |
|-|-|-|-|
| Q1 (most bearish Cu/Au signal) | 303 | 1.49% | 4.28% |
| Q2 | 302 | 0.83% | 4.31% |
| Q3 | 302 | 0.66% | 4.51% |
| Q4 | 302 | 0.93% | 4.33% |
| Q5 (most bullish Cu/Au signal) | 303 | **2.63%** | **7.51%** |

**Note on direction:** After sign inversion, Q5 = strongest bullish signal (most negative raw Cu/Au momentum, i.e., sharpest Cu/Au decline). Q5 delivers 2.63% mean 21d return, highest of all quintiles. Q3 is the lowest (0.66%). The Q5-Q3 spread is 1.97%.

The ordering is NOT perfectly monotonic in walk-forward (Q1 > Q2, but Q4 > Q2). This is weaker than the static OOS quintiles (which were perfectly monotonic). The walk-forward confirms Q5 dominance but shows the middle quintiles are noisy.

## Bonferroni Correction (9 tests)

| Metric | Value |
|-|-|
| T-test p-value on WF ICs | 0.003575 |
| Bonferroni-adjusted p | **0.032** |
| Significant at 5% | **YES** |
| Significant at 1% | NO |
| Significant at 0.1% | NO |

Walk-forward survives Bonferroni at 5% but NOT at 1%. This is weaker than the static OOS result (which survived at 0.1%). Walk-forward is a harder test, and the signal passes the conventional threshold.

## Verdict: CONDITIONAL PASS

The Cu/Au ratio signal **passes walk-forward validation** with the following conditions:

**Strengths:**
1. Walk-forward ICIR of 0.355 with 66.7% of periods showing positive IC
2. L/S Sharpe of 0.98 net of 15bps costs
3. Inverted sign persists across all walk-forward sub-periods
4. NOT a dollar proxy (98.9% IC retained after orthogonalization)
5. Survives Bonferroni at 5%
6. Exceptionally strong in crisis regime (ICIR 1.29)

**Weaknesses:**
1. Fails in risk_on regime (negative IC when VIX < 15)
2. WF quintile ordering is imperfect (not fully monotonic)
3. Bonferroni significance drops from 0.1% (static) to 5% (walk-forward)
4. Second-half WF IC (0.119) is weaker than first-half (0.192), signal decay

**Implementation requirements:**
1. **Regime-conditional only:** Apply signal only when VIX >= 15. Zero weight in risk_on regime.
2. **Use 21-day momentum:** NOT 63-day (the static study found IS/OOS inconsistency at 63d).
3. **Invert sign:** Multiply raw Cu/Au 21d momentum by -1 so positive = bullish.
4. **Suggested weight:** Start at 5% cross-asset weight in risk_off, 10% in crisis. Review after 6 months of live data.
5. **Do NOT orthogonalize:** Raw signal is more stable in walk-forward.

## Multiple-Testing Correction Across the Research Program

The walk-forward p-value (0.003575) was computed within the Cu/Au family. Across the program, 14 signal families had been tested at that point (bond-equity correlation, breadth, breadth multivariate, copper/gold, credit spreads, earnings revision, FII/DII flow, insider trading, options skew, put/call ratio, sector relative strength, short interest, variance risk premium, VIX term structure). Bonferroni over 14 families gives p = 0.050; over roughly 42 sub-tests (about three constructions per family) it gives p = 0.150. The signal survives the family-level correction at exactly 5% and fails the sub-test-level correction. First-half walk-forward IC 0.192 versus second-half 0.119 is a 38% decay over 36 periods each. Lookback sensitivity (15-day, 30-day) was not tested.

## Implementation Record

The signal was implemented in quantshield/signals/copper_gold.py: 21-day percentage change of HG=F/GC=F, sign inverted, rank-normalized, with weight 0.00 in risk_on, 0.10 in risk_off and 0.20 in crisis in the last production configuration, plus a rolling-IC deactivation check. It was later removed from the composite as a zero-contribution signal after the equal-weight null experiment showed the full signal stack indistinguishable from equal weight. Status: conditional, not deployed.
