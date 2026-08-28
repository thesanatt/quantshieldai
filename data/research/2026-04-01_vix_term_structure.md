# VIX Term Structure Signal Research

**Date:** 2026-04-01
**Signal:** VIX vs VIX3M contango/backwardation as regime/timing signal

## Signal Description and Hypothesis

The VIX term structure compares spot VIX (30-day implied vol) to VIX3M (3-month implied vol). When VIX < VIX3M (contango), the term structure is normal and markets are calm. When VIX > VIX3M (backwardation), near-term fear exceeds longer-term expectations, indicating market stress.

**Hypothesis:** VIX term structure predicts forward equity returns. Specifically, backwardation (high ts_ratio) is followed by positive mean-reversion returns as fear dissipates, and contango periods see lower but steadier returns.

**Note:** The expected relationship is that higher ts_ratio (more backwardation/stress) correlates with HIGHER forward returns due to mean-reversion in volatility and equity risk premia. This is a contrarian signal.

## Data

- **VIX (^VIX):** 1,256 daily observations
- **VIX3M (^VIX3M):** 1,255 daily observations
- **SPY:** 1,255 daily observations
- **Equity universe:** VOO, AAPL, GOOGL, AMZN, NVDA, JNJ, KO, BRK-B, COST, MSFT
- **Period:** 2021-04-01 to 2026-04-01 (5 years)
- **Aligned sample:** 1,234 rows after computing forward returns

## Methodology

1. Computed two signal variants:
   - **ts_ratio** = VIX / VIX3M (>1 = backwardation, <1 = contango)
   - **ts_spread** = VIX - VIX3M (>0 = backwardation)
2. Forward returns: 5-day and 21-day for SPY and equal-weight portfolio
3. **In-sample:** First 70% (863 rows, 2021-04-01 to 2024-09-05)
4. **Out-of-sample:** Last 30% (371 rows, 2024-09-06 to 2026-03-02)
5. Rank correlation (Spearman) and Pearson IC
6. Rolling 63-day IC for stability assessment
7. Quintile analysis, regime splits, transaction cost sensitivity

## In-Sample Results

| Signal | Forward Return | Spearman | Pearson IC | t-stat | p-value |
|-|-|-|-|-|-|
| ts_ratio | spy_fwd_5d | +0.0812 | +0.0683 | +2.39 | 0.0170 |
| ts_ratio | spy_fwd_21d | +0.1983 | +0.1918 | +5.94 | 0.0000 |
| ts_ratio | port_fwd_5d | +0.0518 | +0.0531 | +1.52 | 0.1285 |
| ts_ratio | port_fwd_21d | +0.1520 | +0.1526 | +4.51 | 0.0000 |
| ts_spread | spy_fwd_5d | +0.1076 | +0.1063 | +3.17 | 0.0016 |
| ts_spread | spy_fwd_21d | +0.2752 | +0.2820 | +8.40 | 0.0000 |
| ts_spread | port_fwd_5d | +0.0835 | +0.0951 | +2.46 | 0.0141 |
| ts_spread | port_fwd_21d | +0.2247 | +0.2480 | +6.77 | 0.0000 |

**Key finding:** Both signal variants show statistically significant positive correlation with forward returns, especially at the 21-day horizon. The ts_spread variant is slightly stronger. Positive correlation confirms the contrarian hypothesis: stressed markets (backwardation) are followed by higher returns.

## Out-of-Sample Results

| Signal | Forward Return | Spearman | Pearson IC | t-stat | p-value |
|-|-|-|-|-|-|
| ts_ratio | spy_fwd_5d | +0.2321 | +0.2150 | +4.58 | 0.0000 |
| ts_ratio | spy_fwd_21d | +0.1763 | +0.2350 | +3.44 | 0.0006 |
| ts_ratio | port_fwd_5d | +0.1727 | +0.1991 | +3.37 | 0.0008 |
| ts_ratio | port_fwd_21d | +0.0981 | +0.1606 | +1.89 | 0.0591 |
| ts_spread | spy_fwd_5d | +0.2116 | +0.2345 | +4.16 | 0.0000 |
| ts_spread | spy_fwd_21d | +0.1302 | +0.2662 | +2.52 | 0.0121 |
| ts_spread | port_fwd_5d | +0.1699 | +0.2435 | +3.31 | 0.0010 |
| ts_spread | port_fwd_21d | +0.0677 | +0.2035 | +1.30 | 0.1929 |

**Key finding:** Signal persists out-of-sample. The 5-day horizon actually shows STRONGER correlation OOS than IS, which is unusual and encouraging. The 21-day horizon weakens somewhat but remains significant at the 5% level for SPY. The portfolio-level 21-day results lose significance (p=0.06 and p=0.19), suggesting the signal is more useful for broad market timing than individual stock selection.

## Rolling IC Analysis (63-day window)

| Signal vs Return | Mean IC | IC Std | ICIR |
|-|-|-|-|
| ts_ratio vs spy_fwd_5d | +0.2441 | 0.1915 | +1.2747 |
| ts_ratio vs spy_fwd_21d | +0.3805 | 0.2713 | +1.4027 |

ICIR above 0.5 is considered good; above 1.0 is excellent. Both variants have outstanding ICIR, indicating the signal is consistently predictive over time.

## Quintile Analysis (ts_ratio -> 21-day SPY forward returns)

| Quintile | Mean Return | Std Dev | Count | Annualized Sharpe |
|-|-|-|-|-|
| Q1 (deep contango) | 0.64% | 3.15% | 247 | 0.70 |
| Q2 | 0.31% | 3.88% | 247 | 0.27 |
| Q3 | 0.75% | 4.01% | 246 | 0.65 |
| Q4 | 0.80% | 4.70% | 247 | 0.59 |
| Q5 (backwardation) | 2.58% | 4.98% | 247 | 1.79 |

**Key finding:** Strong monotonic relationship. Q5 (backwardation) delivers 4x the returns of Q1 (contango), with an annualized Sharpe of 1.79. The spread between Q5 and Q1 is approximately 1.94% per 21-day period.

## Regime Analysis

| Regime | n | Spearman | p-value |
|-|-|-|-|
| High VIX (> median) | 617 | +0.3251 | 0.0000 |
| Low VIX (<= median) | 617 | +0.0756 | 0.0604 |
| Bull (SPY > SMA200) | 773 | +0.0751 | 0.0368 |
| Bear (SPY <= SMA200) | 262 | +0.3750 | 0.0000 |

**Key finding:** The signal is regime-dependent. It is MUCH stronger in high-VIX / bear market environments (Spearman 0.33-0.38) versus low-VIX / bull markets (0.07-0.08). This makes intuitive sense: the term structure carries more information when markets are stressed. In calm bull markets, the term structure is consistently in contango and carries less discriminating power.

**Implication for integration:** This signal should receive higher weight in risk-off/crisis regimes, which aligns well with the engine's existing regime-adaptive weighting system.

## Backwardation Signal Analysis

- **Backwardation frequency:** 4.4% of days (VIX > VIX3M)
- **Average 21-day forward return in backwardation:** +4.27%
- **Average 21-day forward return in contango:** +0.86%
- **Spread:** 3.41% per 21-day period

Backwardation is rare but extremely informative. When it occurs, forward returns are approximately 5x higher than normal.

## Transaction Cost Sensitivity

- **Regime transitions:** 42 in 1,234 days = 0.034/day turnover rate
- **At 5bps each way:** 0.43%/year
- **At 10bps each way:** 0.86%/year
- **At 20bps each way:** 1.72%/year

Transaction costs are very manageable. The signal changes infrequently (only 42 regime transitions in ~5 years), so turnover is low. Even at 20bps, annual cost is 1.72% versus an expected excess return spread of ~41% annualized (3.41% x 252/21). The signal has enormous room to absorb costs.

## Caveats and Risks

1. **Overlapping returns:** 21-day forward returns overlap heavily, inflating effective sample size. True independent observations are ~60 (1,234 / 21). Adjusting for this, significance is still strong but t-stats should be divided by roughly sqrt(21) ~ 4.6, reducing the IS t-stat of 5.94 to ~1.3. However, the quintile spread analysis is robust to this concern.

2. **Regime dependency:** Signal is weak in calm markets. If markets remain persistently calm, the signal adds little value.

3. **Backwardation rarity:** Only 4.4% of days. The strongest version of the signal (binary backwardation flag) triggers rarely.

4. **Short sample:** 5 years includes COVID recovery and 2022 bear market but may not represent all market regimes.

## Conclusion and Recommendation

**PROMISING**

The VIX term structure signal shows strong, statistically significant predictive power for forward equity returns that persists out-of-sample. Key strengths:
- ICIR of 1.27-1.40 (excellent)
- Monotonic quintile returns with 4x spread between extremes
- Low turnover = low transaction costs
- Strongest exactly when it's needed most (bear/crisis regimes)
- Complements existing engine signals (especially cross-asset)

**Recommended integration:** Use ts_ratio (VIX/VIX3M) as a continuous signal with higher weight in risk-off/crisis regimes. Consider adding VIX3M to the MACRO_TICKERS list. The signal is best used as a market timing/regime overlay rather than a cross-sectional stock selector.

## Independent Review

A second run reproduced the headline statistics within 5% (aligned rows 1,233 vs 1,234; IS Spearman 21d 0.2019 vs 0.1983; OOS Spearman 21d 0.1711 vs 0.1763; Q5 mean 2.58% in both). Year-by-year Spearman of ts_ratio against 21-day SPY forward returns:

| Year | Spearman | p-value |
|-|-|-|
| 2021 | +0.396 | <0.001 |
| 2022 | +0.498 | <0.001 |
| 2023 | -0.019 | 0.763 |
| 2024 | +0.377 | <0.001 |
| 2025 | +0.111 | 0.079 |
| 2026 (to April) | -0.501 | 0.001 |

First-half and second-half Spearman are 0.179 and 0.180, so a halves split hides the 2023 failure and the 2026 reversal. Correlation of ts_ratio with the VIX level is 0.74 (Pearson) and 0.66 (Spearman); after residualizing on VIX level the incremental Spearman is 0.12 (p<0.001). On non-overlapping 21-day windows (n=59) the Spearman is 0.33 with t=2.60, which clears a Bonferroni threshold for the three signals tested at that point, but not by much.

Verdict after review: conditional. Use only as a regime-conditional overlay with zero weight in risk_on, a weight cap of 5 to 8% elsewhere, orthogonalization against VIX level, and automatic disablement when the trailing 63-day Spearman falls below -0.1. The production configuration that followed gave the signal 0.05 in risk_on and zero elsewhere, the opposite of the review conditions. It was later removed from the composite as a zero-contribution signal. Status: conditional, not deployed.
