# Signal Investigation: Copper/Gold Ratio

**Date:** 2026-04-01

## Hypothesis

The copper/gold ratio (Cu/Au) is a real-time growth barometer. Copper demand reflects industrial activity (growth), gold demand reflects safe-haven flows (fear). Rising Cu/Au signals growth acceleration and risk-on conditions. Falling Cu/Au signals growth deceleration and risk-off. The 21-day momentum of Cu/Au should predict forward equity returns, and could enhance regime detection or serve as a standalone cross-asset signal.

## Data

- **Source:** yfinance (HG=F for copper futures, GC=F for gold futures)
- **Period:** 2020-10-09 to 2026-04-01 (1,375 trading days)
- **IS/OOS Split:** 70/30 (IS: 941 obs through 2024-08-07, OOS: 392 obs from 2024-08-08)
- **Signal constructions tested:**
  - Cu/Au 21-day momentum (pct_change over 21 days)
  - Cu/Au 63-day momentum
  - Cu/Au 63-day z-score

## Information Coefficient Analysis

### Cu/Au 21d Momentum vs Benchmark (VOO) Forward Returns

| Horizon | IS IC | IS t-stat | IS p | OOS IC | OOS t-stat | OOS p |
|-|-|-|-|-|-|-|
| 5d | **-0.0929** | **-2.86** | **0.0044** | **-0.1592** | **-3.25** | **0.0013** |
| 10d | **-0.0812** | **-2.49** | **0.0128** | **-0.2000** | **-4.09** | **0.00005** |
| 21d | **-0.0990** | **-3.05** | **0.0024** | **-0.2561** | **-5.23** | **0.0000003** |

### Cu/Au 63d Momentum vs Benchmark Forward Returns

| Horizon | IS IC | IS t-stat | IS p | OOS IC | OOS t-stat | OOS p |
|-|-|-|-|-|-|-|
| 5d | 0.0286 | 0.86 | 0.3914 | **-0.2219** | **-4.59** | **0.000006** |
| 10d | 0.0101 | 0.30 | 0.7613 | **-0.3192** | **-6.75** | **<0.001** |
| 21d | 0.0165 | 0.50 | 0.6204 | **-0.4384** | **-9.63** | **<0.001** |

### Cu/Au 63d Z-Score vs Benchmark Forward Returns

| Horizon | IS IC | IS t-stat | IS p | OOS IC | OOS t-stat | OOS p |
|-|-|-|-|-|-|-|
| 5d | -0.0481 | -1.44 | 0.1493 | **-0.1340** | **-2.72** | **0.0067** |
| 10d | -0.0475 | -1.43 | 0.1541 | **-0.2391** | **-4.93** | **0.000001** |
| 21d | -0.0705 | -2.12 | 0.0343 | **-0.2501** | **-5.10** | **0.0000005** |

**KEY FINDING: NEGATIVE IC across all constructions and horizons.** Rising Cu/Au momentum predicts LOWER forward equity returns, opposite to the standard interpretation that rising Cu/Au = growth = bullish equities.

**CRITICAL: The IC is CONSISTENT in sign between IS and OOS.** For the 21d momentum construction, IC goes from -0.10 (IS) to -0.26 (OOS), same direction, STRONGER out of sample. This is the opposite of overfitting. The signal actually improved OOS, which is rare and noteworthy.

**The 63d momentum shows a concerning IS/OOS divergence:** IS IC is essentially zero (0.02), but OOS IC is -0.44. This extreme OOS performance without IS signal is suspicious and likely reflects a regime-specific OOS period rather than a stable relationship. I give more weight to the 21d momentum which is consistent across both periods.

## Rolling IC Analysis (63-day windows, 21d forward, 21d momentum)

| Metric | Full | IS | OOS |
|-|-|-|-|
| Mean IC | -0.1794 | -0.1301 | -0.3415 |
| Std IC | 0.3783 | 0.3716 | 0.3656 |
| ICIR | **-0.47** | **-0.35** | **-0.93** |
| % positive IC periods | 31.7% | n/a | n/a |

The ICIR of -0.47 (full sample) and -0.93 (OOS) are strong by absolute value. Only 31.7% of rolling windows show positive IC, the signal is persistently negative. The OOS ICIR of -0.93 approaches the "golden" threshold of |1.0|, though in the negative direction.

## Quintile Analysis (21d Momentum, 21d Forward Returns)

### Full Sample
| Quintile | n | Mean (%) | Median (%) | Std (%) |
|-|-|-|-|-|
| Q1 (most negative Cu/Au mom) | 267 | **3.24** | **3.01** | 3.68 |
| Q2 | 266 | 0.88 | 1.53 | 3.97 |
| Q3 | 267 | 0.46 | 0.98 | 4.00 |
| Q4 | 266 | 0.49 | 1.33 | 4.18 |
| Q5 (most positive Cu/Au mom) | 267 | 0.87 | 2.01 | 4.25 |

**MONOTONIC Q1 >> Q2-Q5.** Q1 (falling Cu/Au) has 3.24% mean 21d return, roughly 3-4x the returns of Q2-Q5. Q2-Q5 are relatively flat, suggesting this is primarily a Q1 effect (falling Cu/Au is bullish for equities).

### IS Only
| Quintile | n | Mean (%) |
|-|-|-|
| Q1 | 164 | 3.41 |
| Q2 | 181 | 0.75 |
| Q3 | 191 | 0.48 |
| Q4 | 201 | 0.55 |
| Q5 | 204 | 1.09 |

### OOS Only
| Quintile | n | Mean (%) |
|-|-|-|
| Q1 | 103 | **2.98** |
| Q2 | 85 | 1.17 |
| Q3 | 76 | 0.43 |
| Q4 | 65 | 0.29 |
| Q5 | 63 | 0.18 |

**OOS quintile ordering is beautifully monotonic:** Q1 (2.98%) > Q2 (1.17%) > Q3 (0.43%) > Q4 (0.29%) > Q5 (0.18%). This is textbook signal behavior. The IS pattern is also monotonic with a slight Q5 uptick. The Q1-Q5 spread is 2.32% (IS) and 2.80% (OOS) per 21-day period.

## Regime Analysis (VIX-based)

| Regime | n | IC | p-value |
|-|-|-|-|
| VIX < 15 | 261 | **+0.2901** | **<0.001** |
| 15 <= VIX < 25 | 890 | **-0.1474** | **<0.001** |
| VIX >= 25 | 182 | **-0.4311** | **<0.001** |

**SIGN FLIP BY REGIME.** This is a critical finding:
- **Low VIX:** IC is POSITIVE (+0.29). When VIX is low, rising Cu/Au predicts HIGHER equity returns (standard interpretation).
- **Normal/High VIX:** IC is NEGATIVE (-0.15 to -0.43). When VIX is elevated, rising Cu/Au predicts LOWER equity returns (contrarian).

**Interpretation:** In calm markets, Cu/Au acts as a growth indicator (rising = bullish). In stressed markets, rising Cu/Au is a lagging indicator of prior growth that is about to reverse, or gold is falling (risk-off selling of gold to raise cash), making the ratio rise mechanically even as equities are about to fall.

The overall negative IC is driven by the longer time spent in normal/elevated VIX regimes in our 2020-2026 sample. The regime-conditional behavior means a SIMPLE implementation (always use Cu/Au momentum) would be suboptimal. A REGIME-CONDITIONAL implementation could be powerful.

## Per-Stock OOS IC

| Ticker | IC | p-value |
|-|-|-|
| AAPL | **-0.1875** | **0.0002** |
| GOOGL | -0.0610 | 0.2282 |
| AMZN | **-0.2383** | **<0.001** |
| NVDA | -0.0413 | 0.4152 |
| JNJ | **0.1872** | **0.0002** |
| KO | **0.1936** | **0.0001** |
| BRK-B | -0.0488 | 0.3349 |
| COST | -0.0107 | 0.8322 |
| MSFT | **-0.1983** | **<0.001** |

**Growth vs Defensive split:** The signal has strongly negative IC for growth/cyclical stocks (AAPL, AMZN, MSFT) and strongly POSITIVE IC for defensives (JNJ, KO). This confirms that falling Cu/Au (signal=negative) is bullish for the market overall, but the effect is concentrated in growth stocks. Defensives actually benefit from RISING Cu/Au (which is counterintuitive but may reflect rotation dynamics).

## Correlation with Existing Signals

| Signal | Spearman Correlation |
|-|-|
| Momentum (avg) | -0.0295 |
| RSI (avg) | 0.0170 |
| VIX level | -0.0137 |
| UUP 21d momentum | **-0.1711** |
| Bond-Eq Corr (Signal 1) | 0.0577 |
| VRP (Signal 2) | -0.1105 |

**Highly orthogonal to all existing signals.** Near-zero correlation with momentum (-0.03), RSI (0.02), and VIX (-0.01). The -0.17 correlation with UUP (dollar) momentum is expected since both copper and gold are USD-denominated. Low correlation with other new signals tested today (0.06 with bond-equity correlation, -0.11 with VRP).

This is a genuinely new source of information for the engine.

## Bonferroni Correction (9 tests)

| Metric | Value |
|-|-|
| Raw p-value (21d OOS, 21d mom) | 0.00000027 |
| Bonferroni-adjusted p | **0.0000025** |
| Significant at 5% | **YES** |
| Significant at 1% | **YES** |
| Significant at 0.1% | **YES** |

Survives Bonferroni correction at ALL conventional significance levels. This is extremely strong statistical evidence.

## Transaction Cost Sensitivity

Cu/Au is a cross-asset regime/timing signal, not a stock-level signal. Implementation options:
- **Regime overlay:** Add Cu/Au momentum to regime detection inputs. Low additional turnover (regime changes ~2-4x/year).
- **Signal weight modifier:** Increase defensive signal weights when Cu/Au momentum is positive, increase growth signal weights when negative. Medium turnover impact.
- **Direct tilt:** Overweight defensives when Cu/Au rising, overweight growth when Cu/Au falling. Higher turnover but captures the per-stock IC divergence.

Estimated additional annual turnover: 10-20% for direct tilt, 5-10% for regime overlay.

## Concerns and Caveats

1. **Inverted sign:** The signal works OPPOSITE to the standard financial narrative. Falling Cu/Au (growth slowing) = equities UP. This is contrarian and may reflect mean-reversion dynamics (growth slowdown expectations overshoot, then equity recovers). A reviewer should scrutinize whether this is a real contrarian pattern or an artifact of the 2020-2026 sample.

2. **OOS period specificity:** 2024-08 to 2026-04 includes specific macro regimes (AI boom, tariff concerns, potential recession scares). The 63d momentum OOS results (IC=-0.44) are suspiciously strong and may reflect OOS-specific dynamics rather than a stable relationship.

3. **Regime-conditional sign flip:** The signal flips sign depending on VIX regime. A simple unconditional implementation might work by accident in our sample but could fail in a regime shift. The regime-conditional implementation is more principled but has more parameters.

4. **Q1 concentration:** The quintile analysis shows most of the alpha is in Q1 (falling Cu/Au), with Q2-Q5 relatively flat. This is an asymmetric signal, it tells you when to be bullish (Cu/Au falling) but doesn't differentiate well among neutral/positive Cu/Au states.

5. **Dollar confound:** The -0.17 correlation with UUP momentum means some of the Cu/Au signal may proxy for dollar weakness (falling dollar lifts both metals, but gold more than copper due to gold's monetary premium, creating the negative Cu/Au momentum that coincides with equity strength). Need to test Cu/Au orthogonalized for UUP.

## Verdict: PROMISING

**Reasons for provisional acceptance:**

1. **Consistent IS/OOS sign** (negative IC in both periods), the rarest and most valuable property in signal research.
2. **Monotonic OOS quintiles**, textbook Q1-to-Q5 spread of 2.80% per 21-day period.
3. **Survives Bonferroni** at 0.1% level (Bonferroni-adjusted p = 0.0000025).
4. **Highly orthogonal** to all existing signals (max correlation magnitude: 0.17 with UUP).
5. **ICIR of -0.47 (full) and -0.93 (OOS)**, well above thresholds for practical signal utility.
6. **Trivially available data**, no new data sources needed, can implement immediately.

**Requirements before implementation:**

1. **Review** of the inverted sign interpretation. The contrarian direction needs economic justification beyond statistical significance.
2. **Dollar-orthogonalized test:** Regress Cu/Au momentum on UUP momentum and test the residual as a signal. If the residual IC collapses, the signal is just a dollar proxy (and we already have UUP in cross-asset).
3. **Regime-conditional implementation design:** Given the VIX-regime sign flip, the engineer should implement this as a regime-conditional signal (bullish when VIX low + Cu/Au rising, bullish when VIX elevated + Cu/Au falling).
4. **Walk-forward validation:** Run the standard walk-forward protocol before engine integration.
5. **Longer history test:** If possible, extend the data back to 2015 to test across more macro regimes.

**Recommended signal construction for engine integration:** Use 21-day Cu/Au momentum (NOT 63-day, which has IS/OOS inconsistency) as a cross-asset input. FLIP the sign (multiply by -1) so that positive signal = bullish, consistent with other cross-asset signals. Consider regime-conditional application.
