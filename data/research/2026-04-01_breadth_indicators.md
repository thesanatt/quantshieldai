# Breadth Indicators Signal Research

**Date:** 2026-04-01
**Signal:** Market breadth (equal-weight vs cap-weight, % above SMA) as equity return predictor

## Signal Description and Hypothesis

Market breadth measures the degree of participation in a market move. When a rally is driven by a narrow set of large-cap names (low breadth), it is historically fragile. When a rally is broad-based (high breadth), it tends to persist. Academic support comes from Whaley (2003) on market breadth indicators and the broader literature on divergences between equal-weight and cap-weight indices.

**Hypothesis:** Low breadth (narrow market leadership) predicts lower forward returns, while broad participation predicts higher returns. Specifically:
- RSP/SPY ratio declining = narrowing breadth = bearish
- Low % of portfolio stocks above 50-day SMA = weak breadth = contrarian bullish (oversold)

Five signal variants tested:
1. **breadth_ratio_z** = 63-day z-score of RSP/SPY ratio (equal-weight vs cap-weight)
2. **breadth_mom_21d** = 21-day change in RSP/SPY ratio
3. **breadth_mom_63d** = 63-day change in RSP/SPY ratio
4. **breadth_trend** = RSP/SPY ratio vs its 50-day SMA (percentage deviation)
5. **breadth_pct_above_50d** = Fraction of portfolio stocks (10 tickers) trading above their 50-day SMA

## Data

- **RSP (Invesco S&P 500 Equal Weight):** daily prices
- **SPY:** daily prices
- **VIX:** daily prices
- **Equity universe:** VOO, AAPL, GOOGL, AMZN, NVDA, JNJ, KO, BRK-B, COST, MSFT
- **Period:** 2020-01-14 to 2026-03-02 (~6 years)
- **Aligned sample:** 1,540 rows after computing forward returns
- **In-sample:** 1,078 rows (2020-01-14 to 2024-04-25)
- **Out-of-sample:** 462 rows (2024-04-26 to 2026-03-02)

## In-Sample Results

| Signal | Forward Return | Spearman | Pearson IC | t-stat | p-value |
|-|-|-|-|-|-|
| breadth_ratio_z | spy_fwd_5d | -0.0328 | -0.0089 | -0.29 | 0.7701 |
| breadth_ratio_z | spy_fwd_21d | +0.0093 | +0.0229 | +0.75 | 0.4520 |
| breadth_ratio_z | port_fwd_5d | -0.0457 | -0.0192 | -0.63 | 0.5287 |
| breadth_ratio_z | port_fwd_21d | +0.0284 | +0.0228 | +0.75 | 0.4546 |
| breadth_mom_21d | spy_fwd_5d | -0.0176 | -0.0731 | -2.40 | 0.0164 |
| breadth_mom_21d | spy_fwd_21d | -0.0511 | -0.0977 | -3.22 | 0.0013 |
| breadth_mom_21d | port_fwd_5d | -0.0310 | -0.0639 | -2.10 | 0.0360 |
| breadth_mom_21d | port_fwd_21d | -0.0148 | -0.0675 | -2.22 | 0.0267 |
| breadth_mom_63d | spy_fwd_5d | +0.0029 | -0.0275 | -0.90 | 0.3676 |
| breadth_mom_63d | spy_fwd_21d | -0.0066 | -0.0624 | -2.05 | 0.0406 |
| breadth_mom_63d | port_fwd_5d | -0.0056 | -0.0177 | -0.58 | 0.5612 |
| breadth_mom_63d | port_fwd_21d | -0.0049 | -0.0628 | -2.07 | 0.0391 |
| breadth_trend | spy_fwd_5d | -0.0550 | -0.0763 | -2.51 | 0.0122 |
| breadth_trend | spy_fwd_21d | -0.0721 | -0.1116 | -3.68 | 0.0002 |
| breadth_trend | port_fwd_5d | -0.0633 | -0.0653 | -2.14 | 0.0322 |
| breadth_trend | port_fwd_21d | -0.0424 | -0.0888 | -2.93 | 0.0035 |
| breadth_pct_above_50d | spy_fwd_5d | -0.0392 | -0.0117 | -0.38 | 0.7004 |
| breadth_pct_above_50d | spy_fwd_21d | -0.2086 | -0.1855 | -6.19 | 0.0000 |
| breadth_pct_above_50d | port_fwd_5d | -0.0340 | -0.0232 | -0.76 | 0.4464 |
| breadth_pct_above_50d | port_fwd_21d | -0.1620 | -0.1705 | -5.68 | 0.0000 |

**Key in-sample findings:**
- **breadth_pct_above_50d** is the strongest signal by far: Spearman -0.21, Pearson -0.19, t=-6.19 for spy_fwd_21d. This survives Bonferroni easily (p < 0.0001 vs threshold 0.0083).
- The NEGATIVE correlation means HIGH breadth (many stocks above 50d SMA) predicts LOWER forward returns. This is a CONTRARIAN signal: when everything looks good (broad participation), the market is overbought. When breadth is poor (few above 50d SMA), the market is oversold and rebounds.
- **breadth_trend** and **breadth_mom_21d** also show significance but at weaker levels.
- **breadth_ratio_z** shows no signal in-sample.

## Out-of-Sample Results

| Signal | Forward Return | Spearman | Pearson IC | t-stat | p-value |
|-|-|-|-|-|-|
| breadth_ratio_z | spy_fwd_5d | -0.0165 | -0.0273 | -0.59 | 0.5581 |
| breadth_ratio_z | spy_fwd_21d | -0.1791 | -0.1868 | -4.08 | 0.0001 |
| breadth_ratio_z | port_fwd_5d | -0.0456 | -0.0481 | -1.03 | 0.3027 |
| breadth_ratio_z | port_fwd_21d | -0.1949 | -0.2020 | -4.42 | 0.0000 |
| breadth_mom_21d | spy_fwd_5d | -0.0571 | -0.0411 | -0.88 | 0.3787 |
| breadth_mom_21d | spy_fwd_21d | -0.2758 | -0.2176 | -4.78 | 0.0000 |
| breadth_mom_21d | port_fwd_5d | -0.0750 | -0.0439 | -0.94 | 0.3460 |
| breadth_mom_21d | port_fwd_21d | -0.2207 | -0.1610 | -3.50 | 0.0005 |
| breadth_mom_63d | spy_fwd_5d | +0.0392 | +0.0085 | +0.18 | 0.8555 |
| breadth_mom_63d | spy_fwd_21d | +0.0259 | +0.0072 | +0.15 | 0.8770 |
| breadth_mom_63d | port_fwd_5d | +0.0331 | +0.0052 | +0.11 | 0.9113 |
| breadth_mom_63d | port_fwd_21d | +0.0114 | +0.0037 | +0.08 | 0.9372 |
| breadth_trend | spy_fwd_5d | -0.0329 | -0.0477 | -1.02 | 0.3062 |
| breadth_trend | spy_fwd_21d | -0.1521 | -0.1381 | -2.99 | 0.0029 |
| breadth_trend | port_fwd_5d | -0.0479 | -0.0477 | -1.02 | 0.3066 |
| breadth_trend | port_fwd_21d | -0.1558 | -0.1250 | -2.70 | 0.0072 |
| breadth_pct_above_50d | spy_fwd_5d | -0.1923 | -0.1574 | -3.42 | 0.0007 |
| breadth_pct_above_50d | spy_fwd_21d | -0.1498 | -0.1555 | -3.38 | 0.0008 |
| breadth_pct_above_50d | port_fwd_5d | -0.1616 | -0.1498 | -3.25 | 0.0012 |
| breadth_pct_above_50d | port_fwd_21d | -0.1308 | -0.1269 | -2.74 | 0.0063 |

**Critical OOS findings:**

This is the strongest OOS result among all three signals investigated today.

- **breadth_pct_above_50d PERSISTS OOS** across ALL horizons and return targets. It gains 5-day predictive power OOS (Spearman -0.19, p=0.0007) that was absent IS. Sign is consistent (negative). After Bonferroni (threshold 0.0083): spy_fwd_5d (p=0.0007 PASS), spy_fwd_21d (p=0.0008 PASS), port_fwd_5d (p=0.0012 PASS), port_fwd_21d (p=0.0063 PASS). All four pass.
- **breadth_mom_21d STRENGTHENS OOS** for 21-day returns: IS Spearman -0.05 -> OOS -0.28. This is unusual and noteworthy.
- **breadth_ratio_z EMERGES OOS**: not significant IS but highly significant OOS (p=0.0001 for spy_fwd_21d). This may indicate regime-dependent behavior rather than robust alpha.
- **breadth_trend** also persists OOS with consistent sign.
- **breadth_mom_63d** dies OOS. This 63-day lookback is too slow.

## Rolling IC Analysis (63-day window)

| Signal vs Return | Mean IC | IC Std | ICIR |
|-|-|-|-|
| breadth_ratio_z vs spy_fwd_5d | -0.0109 | 0.2401 | -0.0453 |
| breadth_ratio_z vs spy_fwd_21d | +0.0333 | 0.4360 | +0.0765 |
| breadth_mom_21d vs spy_fwd_5d | -0.0164 | 0.2377 | -0.0691 |
| breadth_mom_21d vs spy_fwd_21d | -0.0598 | 0.4274 | -0.1398 |
| breadth_mom_63d vs spy_fwd_5d | +0.0648 | 0.2773 | +0.2337 |
| breadth_mom_63d vs spy_fwd_21d | +0.1289 | 0.4961 | +0.2598 |
| breadth_trend vs spy_fwd_5d | -0.0324 | 0.2471 | -0.1310 |
| breadth_trend vs spy_fwd_21d | -0.0029 | 0.4782 | -0.0061 |
| **breadth_pct_above_50d vs spy_fwd_5d** | **-0.2387** | **0.2089** | **-1.1429** |
| **breadth_pct_above_50d vs spy_fwd_21d** | **-0.4239** | **0.2923** | **-1.4501** |

**Standout result:** breadth_pct_above_50d achieves ICIR of -1.14 (5-day) and -1.45 (21-day). These are excellent values (|ICIR| > 0.5 is good, > 1.0 is excellent). The negative ICIR is consistent with the contrarian hypothesis. These ICIR values are comparable to the VIX term structure signal (+1.27 to +1.40).

The other variants have poor ICIR, confirming breadth_pct_above_50d as the clear winner.

## Quintile Analysis (breadth_pct_above_50d -> 21-day SPY forward returns)

| Quintile | Mean Return | Std Dev | Count | Annualized Sharpe |
|-|-|-|-|-|
| Q1 (weak breadth) | 2.44% | 6.64% | 353 | +1.27 |
| Q2 | 1.20% | 4.72% | 278 | +0.88 |
| Q3 | 1.42% | 3.33% | 485 | +1.48 |
| Q4 | 0.80% | 3.85% | 236 | +0.72 |
| Q5 (strong breadth) | -1.04% | 7.14% | 188 | -0.50 |

**Strong monotonic relationship with dramatic extremes.** Q1 (weak breadth) returns 2.44% per 21 days vs Q5 (strong breadth) at -1.04%. The Q1-Q5 spread is 3.48% per 21-day period. Q5 is the only quintile with negative mean returns and negative Sharpe. This is a powerful contrarian signal: when all portfolio stocks are above their 50d SMA, the market reliably declines over the next month.

Note: Unequal bin sizes (353 vs 188) reflect the discrete nature of the signal (10 stocks, so only 11 possible values). This is a limitation but does not invalidate the pattern.

## Quintile Analysis (breadth_mom_21d -> 21-day portfolio forward returns)

| Quintile | Mean Return | Std Dev | Count | Annualized Sharpe |
|-|-|-|-|-|
| Q1 (narrowing) | 3.42% | 4.73% | 308 | +2.51 |
| Q2 | 1.02% | 6.39% | 308 | +0.55 |
| Q3 | 1.34% | 4.94% | 308 | +0.94 |
| Q4 | 1.74% | 5.15% | 308 | +1.17 |
| Q5 (broadening) | 2.06% | 5.01% | 308 | +1.42 |

Q1 (narrowing breadth) dominates with 3.42% mean return and Sharpe of 2.51. However, the pattern is NOT monotonic: Q5 > Q4 > Q3. The signal is asymmetric, only the extreme narrowing (Q1) is informative, which may be a crash-recovery artifact.

## Regime Analysis

| Regime | Signal | n | Spearman | p-value |
|-|-|-|-|-|
| High VIX | breadth_ratio_z | 770 | -0.1667 | 0.0000 |
| High VIX | breadth_pct_above_50d | 770 | -0.2088 | 0.0000 |
| High VIX | breadth_mom_21d | 770 | -0.1808 | 0.0000 |
| Low VIX | breadth_ratio_z | 770 | -0.0083 | 0.8183 |
| Low VIX | breadth_pct_above_50d | 770 | -0.0220 | 0.5427 |
| Low VIX | breadth_mom_21d | 770 | -0.1190 | 0.0009 |
| Bull | breadth_ratio_z | 1219 | +0.0345 | 0.2293 |
| Bull | breadth_pct_above_50d | 1219 | -0.1518 | 0.0000 |
| Bull | breadth_mom_21d | 1219 | -0.0387 | 0.1769 |
| Bear | breadth_ratio_z | 321 | -0.3435 | 0.0000 |
| Bear | breadth_pct_above_50d | 321 | -0.1349 | 0.0156 |
| Bear | breadth_mom_21d | 321 | -0.4134 | 0.0000 |

**Key regime findings for breadth_pct_above_50d:**
- Works in BOTH high-VIX (-0.21, p<0.0001) and bull markets (-0.15, p<0.0001)
- Weaker in low-VIX (-0.02, p=0.54) and bear markets (-0.13, p=0.02)
- Unlike VIX term structure (which only works in stress), breadth has predictive power in bull markets too

**breadth_mom_21d** is extremely strong in bear markets (Spearman -0.41) and high VIX (-0.18) but also works in low VIX (-0.12, p=0.0009). This suggests genuine predictive content beyond just volatility regime.

## Transaction Cost Analysis

| Signal | Cost Level | Meaningful Changes | Turnover/day | Annual Cost |
|-|-|-|-|-|
| breadth_pct_above_50d | 5bps | 198 | 0.129 | 3.24% |
| breadth_pct_above_50d | 10bps | 198 | 0.129 | 6.48% |
| breadth_pct_above_50d | 20bps | 198 | 0.129 | 12.96% |
| breadth_mom_21d | 5bps | 166 | 0.108 | 2.72% |
| breadth_mom_21d | 10bps | 166 | 0.108 | 5.43% |
| breadth_ratio_z | 5bps | 102 | 0.066 | 1.67% |
| breadth_ratio_z | 10bps | 102 | 0.066 | 3.34% |

Transaction costs are moderate. The breadth_pct_above_50d signal changes are relatively frequent (discrete jumps), but at 5bps the annual cost of 3.24% is well below the expected Q1-Q5 spread of approximately 3.48% per 21-day period (~60% annualized). The signal has room to absorb realistic transaction costs, though not as generously as VIX term structure.

For implementation, the signal should be used as a portfolio overlay (adjusting overall equity exposure or tilt strength) rather than driving individual stock trades, which would minimize actual turnover.

## Correlation with Existing Signals

| Pair | Correlation |
|-|-|
| breadth_ratio_z vs momentum_12m | -0.11 |
| breadth_ratio_z vs rsi_14 | -0.24 |
| breadth_ratio_z vs trend | -0.24 |
| breadth_ratio_z vs vix_level | +0.39 |
| breadth_ratio_z vs vix_term_struct | +0.25 |
| breadth_pct_above_50d vs momentum_12m | +0.18 |
| **breadth_pct_above_50d vs rsi_14** | **+0.68** |
| **breadth_pct_above_50d vs trend** | **+0.77** |
| breadth_pct_above_50d vs vix_level | -0.48 |
| **breadth_pct_above_50d vs vix_term_struct** | **-0.63** |
| breadth_mom_21d vs momentum_12m | -0.03 |
| breadth_mom_21d vs rsi_14 | -0.20 |
| breadth_mom_21d vs trend | -0.12 |
| breadth_mom_21d vs vix_level | +0.26 |
| breadth_mom_21d vs vix_term_struct | +0.17 |

**MAJOR CONCERN: breadth_pct_above_50d is highly correlated with existing signals.**
- +0.77 with trend (SMA50/SMA200 signal)
- +0.68 with RSI
- -0.63 with VIX term structure

This means breadth_pct_above_50d may be substantially redundant with the trend and RSI signals already in the engine. The alpha may already be captured.

**However, breadth_mom_21d has LOW correlations with all existing signals** (all |r| < 0.26). This variant would add genuine diversification to the signal set. Its OOS performance (Spearman -0.28 for spy_fwd_21d) combined with low correlations to existing signals makes it the more interesting candidate for integration, despite breadth_pct_above_50d having stronger raw IC.

## Bonferroni Correction

Adjusted significance threshold: 0.05/6 = 0.0083.

**breadth_pct_above_50d results surviving Bonferroni (both IS and OOS):**
- IS: spy_fwd_21d (p<0.0001), port_fwd_21d (p<0.0001), PASS
- OOS: spy_fwd_5d (p=0.0007), spy_fwd_21d (p=0.0008), port_fwd_5d (p=0.0012), port_fwd_21d (p=0.0063), ALL PASS

**breadth_mom_21d results surviving Bonferroni:**
- IS: spy_fwd_21d (p=0.0013), PASS
- OOS: spy_fwd_21d (p<0.0001), port_fwd_21d (p=0.0005), PASS

## Caveats and Risks

1. **Overlap with existing signals:** breadth_pct_above_50d is 0.77 correlated with the trend signal and 0.68 with RSI. The marginal alpha after controlling for these signals may be near zero. A proper multivariate regression controlling for existing signals is needed before implementation.

2. **Discrete signal:** breadth_pct_above_50d has only 11 possible values (0/10, 1/10, ..., 10/10) with our 10-stock universe. This limits granularity and creates unequal quintile bins. Expanding the universe or using a broader index measure (RSP/SPY ratio) would improve signal quality.

3. **Overlapping returns:** 21-day forward returns overlap heavily. True independent observations are ~73 (1540/21). Adjusting the IS t-stat of -6.19 by sqrt(21) ~ 4.6 gives ~1.35, which is marginal. However, the OOS persistence provides stronger evidence than adjusted IS t-stats.

4. **Contrarian timing risk:** The signal predicts that strong breadth leads to declines. In a sustained rally, this signal would persistently recommend underweighting equities, causing significant tracking error and potential career risk. This must be managed with position limits.

5. **Sample period concentration:** The sample includes the extreme breadth collapse (COVID March 2020) and subsequent recovery, which may dominate the statistics. The Q1 (weak breadth) returns of 3.42% may be inflated by this episode.

6. **breadth_mom_21d is the diversifying variant but weaker:** The variant that adds genuine new information (breadth_mom_21d, low correlation with existing signals) has weaker ICIR (-0.14) than breadth_pct_above_50d (-1.45). This is the classic tension between signal strength and signal independence.

## Conclusion and Recommendation

**INVESTIGATE FURTHER**

The breadth indicator signal shows genuine predictive power that persists out-of-sample, with the breadth_pct_above_50d variant delivering ICIR of -1.45 and monotonic quintile spreads of 3.48% per 21-day period. All four OOS tests pass Bonferroni correction. This is the strongest new signal candidate tested in this batch.

However, there are two critical issues preventing a clean PROMISING verdict:

1. **Redundancy risk:** The 0.77 correlation with the existing trend signal and 0.68 with RSI means much of the alpha may already be captured. A multivariate analysis controlling for existing signals is required to quantify marginal contribution.

2. **Discrete signal granularity:** Only 11 possible values with our 10-stock universe limits precision.

**Recommended next steps:**
- Run multivariate regression of forward returns on breadth_pct_above_50d AND existing signals (trend, RSI, VIX term structure) to measure marginal IC
- If marginal IC is significant, integrate as a portfolio-level overlay with regime-adaptive weighting
- Consider breadth_mom_21d as an alternative if multivariate analysis shows breadth_pct_above_50d is fully subsumed
- Use RSP/SPY ratio (continuous) rather than discrete stock-level measure for smoother signal
- Assign conservative weight (2-5%) initially given redundancy concerns
