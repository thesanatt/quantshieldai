# Signal Investigation: Variance Risk Premium

**Date:** 2026-04-01

## Hypothesis

The Variance Risk Premium (VRP), defined as implied volatility (VIX) minus realized volatility (21-day SPY annualized), predicts forward equity returns. High VRP means options are expensive relative to actual moves; investors demanding compensation for bearing volatility risk. Per academic literature (Bollerslev, Tauchen, Zhou 2009), high VRP predicts positive forward equity returns. This could serve as a standalone timing signal or regime detection enhancement.

## Data

- **Source:** yfinance (^VIX, SPY daily close)
- **Period:** 2020-10-09 to 2026-04-01 (1,375 trading days)
- **IS/OOS Split:** 70/30 (IS: 879 obs through 2024-08-07, OOS: 392 obs from 2024-08-08)
- **Signal constructions tested:**
  - VRP raw level (implied - realized, in volatility points)
  - VRP z-score (expanding mean/std normalization)

## VRP Descriptive Statistics

| Metric | Value |
|-|-|
| Mean VRP | 4.16% |
| Std | 5.50% |
| % positive (implied > realized) | 87.4% |

VRP is structurally positive, confirming that implied vol persistently exceeds realized vol. The market consistently overprices volatility, which is the well-known volatility risk premium.

## Information Coefficient Analysis

### VRP Z-Score vs Benchmark (VOO) Forward Returns

| Horizon | IS IC | IS t-stat | IS p | OOS IC | OOS t-stat | OOS p |
|-|-|-|-|-|-|-|
| 5d | 0.0334 | 0.99 | 0.3227 | 0.0522 | 1.03 | 0.3026 |
| 10d | -0.0127 | -0.38 | 0.7076 | 0.0150 | 0.30 | 0.7670 |
| 21d | 0.0670 | 1.99 | 0.0470 | -0.0782 | -1.55 | 0.1220 |

### VRP Raw Level vs Benchmark Forward Returns

| Horizon | IS IC | IS t-stat | IS p | OOS IC | OOS t-stat | OOS p |
|-|-|-|-|-|-|-|
| 5d | 0.0128 | 0.38 | 0.7055 | 0.0561 | 1.11 | 0.2674 |
| 10d | -0.0407 | -1.21 | 0.2281 | 0.0175 | 0.34 | 0.7304 |
| 21d | 0.0396 | 1.17 | 0.2406 | -0.0903 | -1.79 | 0.0741 |

**FINDING:** Neither the z-scored nor raw VRP produces meaningful, consistent IC. The IS ICs are already weak (0.04-0.07 with marginal significance). OOS ICs are near zero for 5d and 10d, and flip negative for 21d. The 21d OOS IC of -0.08 (z-score) and -0.09 (raw) suggest that high VRP actually predicts WORSE forward returns in the OOS period, opposite to the academic literature.

**Note on Pearson vs Spearman divergence:** The Pearson ICs show stronger effects (IS 21d: +0.19, OOS 21d: -0.29) due to outlier sensitivity. VRP has fat-tailed distribution, so Spearman is the correct measure. The Pearson sign flip is even larger, driven by a few extreme VRP observations that coincide with market drawdowns.

## Rolling IC Analysis (63-day windows, 21d forward, z-score)

| Metric | Full | IS | OOS |
|-|-|-|-|
| Mean IC | 0.0271 | 0.0736 | -0.0908 |
| Std IC | 0.3591 | 0.3364 | 0.3742 |
| ICIR | 0.08 | 0.22 | -0.24 |
| % positive IC periods | 49.3% | n/a | n/a |

ICIR is anemic. Essentially a coin flip (49.3% of periods have positive IC). IS ICIR of 0.22 is below any reasonable threshold for signal viability (ICIR > 0.5 is typically required). OOS ICIR is negative.

## Quintile Analysis (Raw VRP Level, 21d Forward Returns)

### Full Sample
| Quintile | n | Mean (%) | Median (%) | Std (%) |
|-|-|-|-|-|
| Q1 (lowest VRP) | 255 | 1.23 | 2.28 | 5.05 |
| Q2 | 254 | 1.16 | 2.19 | 4.13 |
| Q3 | 254 | 1.03 | 1.84 | 4.28 |
| Q4 | 254 | 0.40 | 0.82 | 3.70 |
| Q5 (highest VRP) | 254 | 1.80 | 1.80 | 3.73 |

Non-monotonic. Q4 is the worst, Q5 bounces back. The expected monotonic pattern (Q1 worst, Q5 best) is NOT present.

### OOS Only
| Quintile | n | Mean (%) |
|-|-|-|
| Q1 | 77 | 2.82 |
| Q2 | 73 | 0.84 |
| Q3 | 54 | 0.57 |
| Q4 | 87 | 0.26 |
| Q5 | 101 | 1.36 |

OOS quintiles show Q1 (lowest VRP) has the BEST returns, opposite to theory. The pattern is noisy and non-monotonic. Q4 is worst, Q5 recovers. This U-shaped pattern (Q1 and Q5 both good) is inconsistent with a linear signal.

## Regime Analysis (VIX-based)

| Regime | n | IC | p-value |
|-|-|-|-|
| VIX < 15 | 261 | **-0.3756** | **<0.001** |
| 15 <= VIX < 25 | 839 | 0.0765 | 0.0267 |
| VIX >= 25 | 171 | -0.0131 | 0.8648 |

**CRITICAL:** In low-VIX regimes, VRP has STRONGLY NEGATIVE IC (-0.38). This means when VIX is low, high VRP (relative to already-low realized vol) predicts BAD forward returns. This contradicts the academic finding entirely. In normal VIX regimes, there is a weak positive IC (0.08), and in crisis, IC is zero.

The explanation: when VIX is low and VRP is still high, it means realized vol has collapsed even faster than implied vol. This often happens right before a correction (calm before the storm). So high VRP in low-vol regimes is actually a WARNING signal, not a buying signal.

## Per-Stock OOS IC

| Ticker | IC | p-value |
|-|-|-|
| AAPL | 0.0650 | 0.1991 |
| GOOGL | 0.0836 | 0.0983 |
| AMZN | -0.0919 | 0.0690 |
| NVDA | 0.0132 | 0.7946 |
| JNJ | 0.0709 | 0.1610 |
| KO | -0.1616 | 0.0013 |
| BRK-B | **0.1855** | **0.0002** |
| COST | -0.1445 | 0.0041 |
| MSFT | **-0.2031** | **<0.001** |

Mixed results. BRK-B shows strong positive IC (high VRP = buy BRK-B), while MSFT and COST show negative IC. KO also negative. No consistent stock-level pattern.

## Correlation with Existing Signals

| Signal | Spearman Correlation |
|-|-|
| Momentum (avg) | 0.0892 |
| RSI (avg) | -0.1926 |
| VIX level | -0.0393 |
| Bond-Eq Corr (Signal 1) | -0.1265 |

Low correlations across the board. VRP is somewhat orthogonal, though the -0.19 correlation with RSI suggests some overlap (both are contrarian indicators). Surprisingly low correlation with VIX level (-0.04), which means VRP captures something different from VIX itself.

## Transaction Cost Sensitivity

VRP is a market-level timing signal applied as a regime overlay. Impact on portfolio turnover depends on implementation:
- As a continuous signal weight modifier: minimal additional turnover
- As a regime switch (high VRP = risk-on, low VRP = risk-off): ~2-4 switches per year
- Estimated additional annual turnover: 5-10%

Since VRP is structurally positive (87.4% of days), a threshold-based approach would rarely trigger risk-off signals, limiting practical utility.

## Bonferroni Correction (9 tests)

| Metric | Value |
|-|-|
| Raw p-value (21d OOS z-score) | 0.1220 |
| Bonferroni-adjusted p | 1.0000 |
| Significant at 5% | NO |
| Significant at 10% | NO |

Does not survive even raw significance at the 5% level, let alone Bonferroni correction.

## Why the Academic Literature Result Doesn't Replicate

1. **Sample period:** Bollerslev et al. (2009) used 1990-2007. Our sample (2020-2026) includes structurally different regimes (COVID crash, 2022 inflation, AI boom).
2. **VRP structural shift:** Post-2020, the Fed's aggressive intervention compressed VRP. The VIX-realized vol relationship changed structurally.
3. **Frequency mismatch:** Academic results are strongest at MONTHLY frequency with monthly VRP. Our daily VRP is noisier.
4. **Universe:** Academic literature uses SPX returns. We test on individual stocks and VOO.
5. **Structurally positive VRP:** VRP > 0 in 87.4% of days. A signal that is almost always "on" provides very little timing information.

## Verdict: REJECT

**Reasons for rejection:**

1. **No statistically significant OOS IC** at any horizon for either signal construction (z-score or raw level).
2. **Fails Bonferroni correction** comprehensively (adjusted p = 1.0).
3. **Non-monotonic quintiles**, Q1 (lowest VRP) outperforms Q5 (highest VRP) out of sample.
4. **Regime-conditional sign flip**, IC is strongly NEGATIVE when VIX is low, contradicting the core hypothesis.
5. **ICIR < 0.1**, Well below any practical threshold for signal adoption.
6. **Structurally positive**, The signal provides almost no variation (87% of days positive), limiting timing utility.

**Not salvageable.** The variance risk premium may work at monthly/quarterly horizons in broader equity indices, but it does not translate to daily signal construction for our universe and rebalancing frequency. The regime-conditional analysis reveals that the VRP-return relationship is highly non-linear and regime-dependent in ways that make it unreliable as a systematic signal.
