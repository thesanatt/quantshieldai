# Credit Spreads (HY-IG) Signal Research

**Date:** 2026-04-01
**Signal:** High-yield vs investment-grade credit spread as equity return predictor

## Signal Description and Hypothesis

Credit spreads measure the difference in yield (proxied by price returns) between high-yield (HYG) and investment-grade (LQD) corporate bonds. Widening credit spreads indicate deteriorating credit conditions and rising default risk, which academic literature (Gilchrist & Zakrajsek 2012, "Credit Spreads and Business Cycle Fluctuations") shows predicts economic downturns and equity drawdowns.

**Hypothesis:** When credit spreads widen (HY underperforms IG), forward equity returns are lower. When spreads tighten (HY outperforms IG), forward equity returns are higher. Additionally, the HYG/LQD ratio z-score should capture mean-reverting dynamics where extreme cheapness in HY predicts recovery.

Three signal variants tested:
1. **credit_spread_daily** = LQD daily return - HYG daily return (positive = widening)
2. **credit_spread_21d** = 21-day rolling sum of daily spreads (smoothed trend)
3. **credit_ratio_z** = 63-day z-score of HYG/LQD price ratio (positive = HY expensive relative to IG)

## Data

- **HYG (iShares High Yield Corporate Bond):** daily prices
- **LQD (iShares Investment Grade Corporate Bond):** daily prices
- **SPY:** daily prices
- **Equity universe:** VOO, AAPL, GOOGL, AMZN, NVDA, JNJ, KO, BRK-B, COST, MSFT
- **Period:** 2020-01-14 to 2026-03-02 (~6 years)
- **Aligned sample:** 1,540 rows after computing forward returns
- **In-sample:** 1,078 rows (2020-01-14 to 2024-04-25)
- **Out-of-sample:** 462 rows (2024-04-26 to 2026-03-02)

## In-Sample Results

| Signal | Forward Return | Spearman | Pearson IC | t-stat | p-value |
|-|-|-|-|-|-|
| credit_spread_daily | spy_fwd_5d | +0.0400 | +0.1246 | +4.12 | 0.0000 |
| credit_spread_daily | spy_fwd_21d | +0.0332 | +0.0621 | +2.04 | 0.0416 |
| credit_spread_daily | port_fwd_5d | +0.0364 | +0.1085 | +3.58 | 0.0004 |
| credit_spread_daily | port_fwd_21d | +0.0322 | +0.0690 | +2.27 | 0.0235 |
| credit_spread_21d | spy_fwd_5d | +0.0867 | +0.0664 | +2.18 | 0.0294 |
| credit_spread_21d | spy_fwd_21d | +0.0564 | +0.0620 | +2.04 | 0.0420 |
| credit_spread_21d | port_fwd_5d | +0.1032 | +0.1000 | +3.30 | 0.0010 |
| credit_spread_21d | port_fwd_21d | +0.0772 | +0.1071 | +3.53 | 0.0004 |
| credit_ratio_z | spy_fwd_5d | -0.1415 | -0.0877 | -2.89 | 0.0039 |
| credit_ratio_z | spy_fwd_21d | -0.1474 | -0.0837 | -2.76 | 0.0059 |
| credit_ratio_z | port_fwd_5d | -0.1737 | -0.1368 | -4.53 | 0.0000 |
| credit_ratio_z | port_fwd_21d | -0.1952 | -0.1648 | -5.48 | 0.0000 |

In-sample, all three variants show statistically significant correlations. The credit_ratio_z is strongest, with negative correlations indicating that when HY is expensive relative to IG (complacency), forward returns are lower. The credit_spread variants show positive correlations: when spreads widen (stress), near-term returns tend to be positive (contrarian/mean-reversion).

## Out-of-Sample Results

| Signal | Forward Return | Spearman | Pearson IC | t-stat | p-value |
|-|-|-|-|-|-|
| credit_spread_daily | spy_fwd_5d | +0.0521 | -0.0328 | -0.70 | 0.4818 |
| credit_spread_daily | spy_fwd_21d | +0.0517 | -0.0150 | -0.32 | 0.7481 |
| credit_spread_daily | port_fwd_5d | +0.0392 | -0.0347 | -0.74 | 0.4575 |
| credit_spread_daily | port_fwd_21d | +0.0741 | +0.0101 | +0.22 | 0.8290 |
| credit_spread_21d | spy_fwd_5d | -0.0279 | -0.0723 | -1.56 | 0.1205 |
| credit_spread_21d | spy_fwd_21d | -0.1596 | -0.1937 | -4.24 | 0.0000 |
| credit_spread_21d | port_fwd_5d | +0.0212 | -0.0044 | -0.09 | 0.9248 |
| credit_spread_21d | port_fwd_21d | -0.0944 | -0.1442 | -3.13 | 0.0019 |
| credit_ratio_z | spy_fwd_5d | -0.0274 | +0.0006 | +0.01 | 0.9894 |
| credit_ratio_z | spy_fwd_21d | +0.0348 | +0.0262 | +0.56 | 0.5739 |
| credit_ratio_z | port_fwd_5d | -0.0263 | -0.0309 | -0.66 | 0.5076 |
| credit_ratio_z | port_fwd_21d | +0.0214 | +0.0276 | +0.59 | 0.5534 |

**Critical finding: Massive OOS degradation.** The credit_ratio_z signal completely collapses out-of-sample. All p-values > 0.50. The credit_spread_daily also loses all significance. The credit_spread_21d shows a SIGN FLIP for the 21-day horizon (from +0.06 IS to -0.19 OOS), which is significant but in the opposite direction. This is a red flag for instability, not a robust signal.

## Rolling IC Analysis (63-day window)

| Signal vs Return | Mean IC | IC Std | ICIR |
|-|-|-|-|
| credit_ratio_z vs spy_fwd_5d | -0.1292 | 0.2429 | -0.5318 |
| credit_ratio_z vs spy_fwd_21d | -0.0754 | 0.4281 | -0.1762 |
| credit_spread_21d vs spy_fwd_5d | +0.0791 | 0.2348 | +0.3369 |
| credit_spread_21d vs spy_fwd_21d | -0.0334 | 0.4010 | -0.0833 |

ICIR values are poor. The credit_ratio_z has ICIR of -0.53 at 5-day (wrong direction for our hypothesis) and -0.18 at 21-day. The credit_spread_21d has ICIR of only +0.34 at 5-day and essentially zero at 21-day. For reference, the VIX term structure signal achieved ICIR of +1.27 to +1.40. These numbers are not competitive.

## Quintile Analysis (credit_ratio_z -> 21-day SPY forward returns)

| Quintile | Mean Return | Std Dev | Count | Annualized Sharpe |
|-|-|-|-|-|
| Q1 (low HY/IG) | 1.63% | 7.23% | 308 | +0.78 |
| Q2 | 1.86% | 5.30% | 308 | +1.22 |
| Q3 | 0.80% | 4.08% | 308 | +0.68 |
| Q4 | 0.51% | 4.25% | 308 | +0.41 |
| Q5 (high HY/IG) | 1.29% | 4.40% | 308 | +1.02 |

Non-monotonic relationship. Q2 has the highest returns, not Q1 or Q5. Q4 has the lowest. There is no clean Q1-to-Q5 spread to exploit.

## Quintile Analysis (credit_spread_21d -> 21-day SPY forward returns)

| Quintile | Mean Return | Std Dev | Count | Annualized Sharpe |
|-|-|-|-|-|
| Q1 (tight) | 1.17% | 4.71% | 308 | +0.86 |
| Q2 | 1.71% | 4.11% | 308 | +1.44 |
| Q3 | 1.38% | 3.98% | 308 | +1.20 |
| Q4 | 1.01% | 4.16% | 308 | +0.84 |
| Q5 (wide) | 0.82% | 7.93% | 308 | +0.36 |

Weakly monotonically decreasing from Q2 onward, but Q1 breaks the pattern. The Q5-Q1 spread is -0.35%, which contradicts the contrarian hypothesis (wide spreads should predict higher returns). The Sharpe spread is dramatic (Q2=1.44 vs Q5=0.36) but this is driven by the high-vol regime in Q5, not alpha.

## Regime Analysis

| Regime | Signal | n | Spearman | p-value |
|-|-|-|-|-|
| High VIX | credit_ratio_z | 770 | -0.1551 | 0.0000 |
| High VIX | credit_spread_21d | 770 | +0.0554 | 0.1246 |
| Low VIX | credit_ratio_z | 770 | -0.0758 | 0.0355 |
| Low VIX | credit_spread_21d | 770 | -0.0217 | 0.5481 |
| Bull | credit_ratio_z | 1219 | -0.0436 | 0.1283 |
| Bull | credit_spread_21d | 1219 | -0.0161 | 0.5751 |
| Bear | credit_ratio_z | 321 | -0.2735 | 0.0000 |
| Bear | credit_spread_21d | 321 | +0.0936 | 0.0942 |

The credit_ratio_z shows some signal in high-VIX and bear regimes, but the OOS failure overrides this. The credit_spread_21d is insignificant in all regimes except weakly in bear markets.

## Transaction Cost Analysis

Credit_ratio_z threshold crossing analysis:
- 307 threshold crosses (|delta-z| > 0.5) in 1,540 days = 0.20/day turnover
- Mean daily |delta-z|: 0.32
- At 5bps each way: 5.02%/year
- At 10bps each way: 10.05%/year
- At 20bps each way: 20.09%/year

Transaction costs are prohibitively high. The z-score is noisy and changes frequently, generating excessive turnover. Even at 5bps, annual costs of 5% would dwarf any alpha (which is already near-zero OOS).

## Correlation with Existing Signals

| Pair | Correlation |
|-|-|
| credit_ratio_z vs momentum_12m | +0.01 |
| credit_ratio_z vs rsi_14 | -0.09 |
| credit_ratio_z vs trend | +0.02 |
| credit_ratio_z vs vix_level | +0.02 |
| credit_ratio_z vs vix_term_struct | +0.02 |
| credit_spread_21d vs momentum_12m | +0.04 |
| credit_spread_21d vs rsi_14 | +0.07 |
| credit_spread_21d vs trend | -0.01 |
| credit_spread_21d vs vix_level | -0.08 |
| credit_spread_21d vs vix_term_struct | -0.06 |

Low correlations with existing signals (all < 0.10 in absolute terms), which is the one positive finding, it would be diversifying IF it worked. But a zero-alpha signal that is uncorrelated is still worthless.

## Bonferroni Correction

With 6 signal families tested to that point (momentum variants, RSI, SMA trend, cross-asset, earnings, VIX term structure, plus the 3 in this batch), the adjusted significance threshold is 0.05/6 = 0.0083. The credit_ratio_z in-sample results for port_fwd_21d (p=0.0000) pass Bonferroni IS, but ALL OOS results fail at any reasonable threshold.

## Caveats and Risks

1. **Proxy limitations:** HYG/LQD is a return-based proxy for credit spreads, not the actual OAS spread. ETF flows, duration differences, and liquidity premia contaminate the signal.
2. **OOS failure is definitive:** The complete collapse from IS to OOS across all variants and horizons is the strongest possible evidence of overfitting or regime shift.
3. **Sign instability:** The credit_spread_21d signal FLIPS SIGN between IS and OOS at the 21-day horizon. This is not a weak signal, it is an unreliable one.
4. **Overlapping returns caveat applies:** 21-day forward returns overlap, inflating IS significance. True independent observations ~73 (1540/21). This makes the IS results even less impressive.
5. **2024-2026 regime:** The OOS period coincides with a specific macro environment (rate cuts, credit tightening cycle end) that may differ from IS period. However, a robust signal should work across regimes.

## Conclusion and Recommendation

**REJECT**

The credit spread signal fails the most important test: out-of-sample validation. Despite strong academic backing and significant in-sample correlations, every signal variant collapses OOS. The credit_ratio_z goes from t-stat of -5.48 in-sample to +0.59 out-of-sample. The credit_spread_21d flips sign. Quintile analysis is non-monotonic. Transaction costs are prohibitive. The HYG/LQD ETF proxy may be too noisy to capture the underlying credit spread dynamics that work in the academic literature (which typically uses OAS or CDS data). This signal should not be integrated into the engine without access to better data sources (e.g., ICE BofA indices via FRED).
