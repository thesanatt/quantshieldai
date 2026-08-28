# Signal Investigation: Bond-Equity Correlation Regime

**Date:** 2026-04-01

## Hypothesis

Rolling 63-day correlation between SPY and TLT daily returns serves as a regime indicator. When correlation is positive (stocks and bonds move together), the market is in an inflationary regime where traditional diversification fails. When correlation is negative, standard risk-off hedging works. The z-score of this rolling correlation predicts forward equity returns and can improve regime detection.

## Data

- **Source:** yfinance (SPY, TLT daily close)
- **Period:** 2020-10-09 to 2026-04-01 (1,375 trading days)
- **IS/OOS Split:** 70/30 (IS: 2020-10-12 to 2024-08-07, OOS: 2024-08-08 to 2026-04-01)
- **Signal:** Z-score of 63-day rolling SPY-TLT correlation (expanding mean/std normalization)

## Rolling Correlation Statistics

| Metric | Value |
|-|-|
| Mean correlation | 0.0423 |
| Std | 0.2125 |
| Min | -0.4818 |
| Max | 0.4353 |
| % positive | 58.2% |
| % negative | 41.8% |

The correlation has been positive more often than not in our sample (2020-2026), reflecting the inflationary regime post-2022 where stocks and bonds sold off together.

## Information Coefficient Analysis

### Spearman IC vs Benchmark (VOO) Forward Returns

| Horizon | IS IC | IS t-stat | IS p | OOS IC | OOS t-stat | OOS p |
|-|-|-|-|-|-|-|
| 5d | -0.0021 | -0.06 | 0.9510 | -0.0729 | -1.44 | 0.1502 |
| 10d | 0.0175 | 0.50 | 0.6142 | -0.1089 | -2.16 | 0.0311 |
| 21d | **0.1010** | **2.93** | **0.0034** | **-0.1358** | **-2.71** | **0.0071** |

**CRITICAL FINDING: The signal FLIPS SIGN between IS and OOS.** In-sample, higher correlation z-score predicts higher forward returns (IC = +0.10). Out-of-sample, it predicts LOWER forward returns (IC = -0.14). This is a textbook sign-flip failure. The OOS result is statistically significant but in the OPPOSITE direction from IS.

### Pearson IC (21d horizon)

| Sample | Pearson IC | p-value |
|-|-|-|
| IS | 0.1046 | 0.0024 |
| OOS | -0.2242 | 0.000007 |

The Pearson IC sign flip is even more extreme (IS +0.10, OOS -0.22).

## Rolling IC Analysis (63-day windows, 21d forward returns)

| Metric | Full | IS | OOS |
|-|-|-|-|
| Mean IC | -0.0646 | -0.0082 | -0.2131 |
| Std IC | 0.4037 | 0.4114 | 0.3989 |
| ICIR | -0.16 | -0.02 | -0.53 |
| % positive IC periods | 41.9% | n/a | n/a |

The ICIR is negative across the board. The OOS ICIR of -0.53 confirms the signal is working in the WRONG direction out of sample. Only 41.9% of rolling windows show positive IC.

## Quintile Analysis (Raw Correlation Level, 21d Forward Returns)

### Full Sample
| Quintile | n | Mean (%) | Median (%) | Std (%) |
|-|-|-|-|-|
| Q1 (most negative corr) | 246 | 0.89 | 1.39 | 4.02 |
| Q2 | 246 | 0.19 | 0.78 | 4.50 |
| Q3 | 245 | 1.15 | 1.97 | 4.65 |
| Q4 | 246 | 2.09 | 2.75 | 3.95 |
| Q5 (most positive corr) | 246 | 0.84 | 1.57 | 3.86 |

Full sample shows NO monotonic relationship. Q4 is best, not Q1 or Q5.

### OOS Only
| Quintile | n | Mean (%) |
|-|-|-|
| Q1 | 62 | 1.35 |
| Q2 | 97 | 1.79 |
| Q3 | 123 | 1.83 |
| Q4 | 76 | 0.95 |
| Q5 | 34 | -2.53 |

OOS quintiles show a DIFFERENT pattern from IS: Q5 (highest positive correlation) performs worst (-2.53%), while Q2-Q3 perform best. This is a monotonically DECREASING pattern, opposite to the IS Q4-peak pattern. The non-stationarity of the quintile ordering is a fatal flaw.

## Regime Analysis (VIX-based)

| Regime | n | IC | p-value |
|-|-|-|-|
| VIX < 15 | 261 | **0.2352** | **0.0001** |
| 15 <= VIX < 25 | 802 | -0.0234 | 0.5070 |
| VIX >= 25 | 166 | 0.0692 | 0.3756 |

The signal shows strong positive IC only in low-VIX environments. In normal and high-VIX regimes, IC is essentially zero. This means the signal works when you DON'T need regime detection (calm markets) and fails when you DO need it (volatile markets).

## Per-Stock OOS IC

| Ticker | IC | p-value |
|-|-|-|
| AAPL | -0.1288 | 0.0107 |
| GOOGL | **-0.3924** | **<0.001** |
| AMZN | **-0.3865** | **<0.001** |
| NVDA | 0.0131 | 0.7966 |
| JNJ | **0.3154** | **<0.001** |
| KO | **0.2130** | **<0.001** |
| BRK-B | 0.0127 | 0.8027 |
| COST | -0.1325 | 0.0086 |
| MSFT | 0.0212 | 0.6759 |

Interesting divergence: the signal has OPPOSITE effects on growth (GOOGL, AMZN: strongly negative IC) vs defensive (JNJ, KO: strongly positive IC). This suggests the correlation regime signal is really a growth/value rotation indicator, not a market-level timing signal. When bond-equity correlation rises (inflationary regime), defensives outperform growth stocks.

## Correlation with Existing Signals

| Signal | Spearman Correlation |
|-|-|
| Momentum (avg) | -0.1226 |
| RSI (avg) | -0.0072 |
| VIX level | -0.0853 |

Low correlations with all existing signals. The signal IS somewhat orthogonal, which is the one positive finding.

## Transaction Cost Sensitivity

- Average monthly regime flips: 0.42 (one flip every ~2.4 months)
- This is a regime overlay, not stock-level. Turnover impact is through regime weight changes.
- Estimated additional annual turnover: 5-15% depending on regime weight differential.

## Bonferroni Correction (9 tests: 3 signals x 3 horizons)

| Metric | Value |
|-|-|
| Raw p-value (21d OOS) | 0.0071 |
| Bonferroni-adjusted p | 0.0639 |
| Significant at 5% | NO |
| Significant at 10% | YES |

The signal survives Bonferroni correction at the 10% level but NOT the 5% level. However, the sign flip makes this moot, statistical significance in the wrong direction is worse than no signal at all.

## Verdict: REJECT

**Reasons for rejection:**

1. **IS/OOS sign flip**, The most damning finding. IC is +0.10 in-sample and -0.14 out-of-sample. The signal is unstable across time.
2. **Non-monotonic quintiles**, No consistent ordering between IS and OOS quintile returns.
3. **Regime-dependent**, Only works when VIX < 15, which is precisely when regime detection is least needed.
4. **Non-stationary correlation**, The SPY-TLT correlation regime itself shifts (post-2022 structurally positive), so a z-score based on expanding window fails to adapt.

**Salvageable elements:** The per-stock analysis reveals that the correlation regime IS informative for growth/value rotation (GOOGL, AMZN vs JNJ, KO). A future investigation could use the correlation regime as a sector rotation signal rather than a market timing signal. This would require a different signal construction (per-stock beta to TLT, not aggregate correlation) and belongs in a separate investigation.
