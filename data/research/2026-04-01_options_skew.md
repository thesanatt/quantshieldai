# Options Skew (CBOE SKEW Index) Signal Research

**Date:** 2026-04-01
**Signal:** CBOE SKEW Index (^SKEW) as equity return predictor

## Signal Description and Hypothesis

The CBOE SKEW Index measures the perceived tail risk of the S&P 500 by pricing the skewness of S&P 500 options. Higher SKEW values indicate the market is pricing a higher probability of extreme left-tail (crash) events. The index typically ranges from 100 to 150+.

**Primary hypothesis (contrarian):** Elevated SKEW reflects excessive fear-of-crash pricing. When the market over-prices tail risk, forward returns tend to be higher (the insurance premium is too expensive). Conversely, low SKEW suggests complacency.

**Alternative hypothesis (informational):** High SKEW may reflect informed options traders correctly anticipating elevated crash risk, making it a bearish signal.

Six signal variants tested:
1. **skew_z63** = 63-day z-score of SKEW level
2. **skew_z126** = 126-day z-score of SKEW level
3. **skew_pctile** = 252-day rolling percentile rank
4. **skew_mom_21d** = 21-day SKEW momentum (% change)
5. **skew_mom_63d** = 63-day SKEW momentum (% change)
6. **skew_level** = Raw SKEW level

## Data

- **SKEW data:** 1,474 rows, 2020-03-23 to 2026-03-31
- **SKEW range:** 110.3 to 183.1, mean 139.6
- **Aligned sample:** 1,202 rows (2021-03-22 to 2026-03-02)
- **IS:** 841 rows | **OOS:** 361 rows
- **Bonferroni threshold:** 0.05 / 8 = 0.00625 (8 signal families tested to date)

## In-Sample IC Analysis

| Signal | fwd_5d Spearman (p) | fwd_21d Spearman (p) | port_fwd_5d Spearman (p) | port_fwd_21d Spearman (p) |
|-|-|-|-|-|
| skew_z63 | -0.006 (0.869) | -0.024 (0.481) | +0.020 (0.558) | -0.020 (0.560) |
| skew_z126 | -0.006 (0.854) | +0.003 (0.937) | +0.034 (0.328) | +0.026 (0.452) |
| skew_pctile | +0.031 (0.372) | +0.075 (0.030) | +0.070 (0.043) | +0.086 (0.012) |
| skew_mom_21d | +0.007 (0.841) | +0.021 (0.541) | +0.027 (0.441) | -0.002 (0.954) |
| skew_mom_63d | -0.057 (0.099) | -0.074 (0.033) | -0.035 (0.318) | -0.057 (0.100) |
| skew_level | -0.007 (0.835) | -0.017 (0.631) | +0.013 (0.704) | -0.046 (0.182) |

**IS verdict:** No signal variant passes Bonferroni in-sample. The strongest IS result is skew_pctile vs port_fwd_21d (Spearman +0.086, p=0.012), which does NOT survive Bonferroni (threshold 0.00625). All z-score and momentum variants show near-zero IS correlation.

## Out-of-Sample IC Analysis

| Signal | fwd_5d Spearman (p) | fwd_21d Spearman (p) | port_fwd_5d Spearman (p) | port_fwd_21d Spearman (p) |
|-|-|-|-|-|
| skew_z63 | +0.088 (0.097) | +0.097 (0.065) | +0.111 (0.036) | +0.073 (0.169) |
| skew_z126 | +0.014 (0.795) | -0.079 (0.132) | +0.065 (0.218) | -0.065 (0.216) |
| skew_pctile | -0.098 (0.064) | **-0.252 (0.000001)** | -0.048 (0.366) | **-0.263 (0.000000)** |
| skew_mom_21d | +0.023 (0.670) | +0.065 (0.216) | +0.077 (0.146) | +0.048 (0.367) |
| skew_mom_63d | +0.006 (0.916) | -0.061 (0.245) | +0.060 (0.257) | +0.001 (0.988) |
| skew_level | -0.090 (0.088) | **-0.245 (0.000002)** | -0.031 (0.555) | **-0.238 (0.000005)** |

**Critical OOS findings:**

1. **skew_pctile SIGN FLIPS between IS and OOS.** IS: +0.075 (higher percentile = higher returns). OOS: -0.252 (higher percentile = LOWER returns). This is a fatal instability. The signal literally reverses direction.

2. **skew_level shows significance OOS** (Spearman -0.245 for fwd_21d, p=0.000002) but was dead IS (Spearman -0.017, p=0.631). An IS-dead/OOS-alive signal is unreliable, it suggests regime dependence rather than structural alpha.

3. **skew_z63 flips sign** from IS (-0.024) to OOS (+0.097) for fwd_21d. Inconsistent.

4. **No variant shows consistent IS AND OOS significance.** This is the fundamental problem.

## Rolling IC Analysis (63-day window, vs fwd_21d)

| Signal | Mean IC | IC Std | ICIR |
|-|-|-|-|
| skew_z63 | -0.101 | 0.343 | -0.29 |
| skew_z126 | -0.138 | 0.359 | -0.38 |
| skew_pctile | -0.157 | 0.363 | -0.43 |
| skew_mom_21d | -0.066 | 0.354 | -0.19 |
| skew_mom_63d | -0.189 | 0.332 | -0.57 |
| skew_level | -0.210 | 0.328 | -0.64 |

ICIR values are uniformly poor (all |ICIR| < 0.65). For comparison, breadth_pct_above_50d achieved ICIR of -1.45. The best here (skew_level at -0.64) is marginal at best.

## Quintile Analysis (vs fwd_21d, full sample)

### skew_z63

| Quintile | Mean Return | Std Dev | Count | Sharpe |
|-|-|-|-|-|
| Q1 (low z) | +0.95% | 5.25% | 241 | +0.63 |
| Q2 | +1.82% | 4.23% | 240 | +1.49 |
| Q3 | +0.77% | 4.07% | 240 | +0.66 |
| Q4 | +0.76% | 3.96% | 240 | +0.66 |
| Q5 (high z) | +1.23% | 3.86% | 241 | +1.10 |

**No monotonic relationship.** Q2 outperforms, not Q1 or Q5. Pattern is random.

### skew_level

| Quintile | Mean Return | Std Dev | Count | Sharpe |
|-|-|-|-|-|
| Q1 (low SKEW) | +0.65% | 5.70% | 241 | +0.40 |
| Q2 | +2.08% | 4.77% | 240 | +1.51 |
| Q3 | +0.91% | 4.02% | 240 | +0.79 |
| Q4 | +1.25% | 3.03% | 240 | +1.43 |
| Q5 (high SKEW) | +0.63% | 3.36% | 241 | +0.65 |

**No monotonic relationship.** Q2 dominates again. Both extremes (Q1 and Q5) underperform. This suggests a non-linear (humped) relationship, not a tradeable signal.

## Regime Analysis (vs fwd_21d)

| Regime | skew_z63 Spearman (p) | skew_z126 Spearman (p) | skew_mom_21d Spearman (p) |
|-|-|-|-|
| High VIX (n=601) | -0.065 (0.109) | -0.045 (0.270) | -0.007 (0.868) |
| Low VIX (n=601) | +0.137 (0.001) | +0.015 (0.723) | +0.101 (0.013) |
| Bull (n=999) | +0.121 (0.000) | +0.065 (0.039) | +0.072 (0.023) |
| Bear (n=203) | -0.240 (0.001) | -0.288 (0.000) | -0.043 (0.545) |

**SKEW sign-flips by regime.** In bull/low-VIX markets, higher SKEW z-score predicts higher returns (+0.137). In bear markets, higher SKEW predicts lower returns (-0.240). This makes the full-sample IC wash out to near-zero. A regime-conditional implementation could capture this, but the bear-market sample (n=203) is too small for reliable inference.

## Transaction Cost Analysis

| Signal | Cost | Turnover/day | Annual Cost |
|-|-|-|-|
| skew_z63 | 5bps | 0.499 | 6.29% |
| skew_z63 | 10bps | 0.499 | 12.58% |
| skew_z63 | 20bps | 0.499 | 25.16% |

Transaction costs are severe due to the high-frequency signal changes. Even at 5bps, the 6.29% annual cost exceeds any plausible alpha from this signal.

## Correlation with Existing Signals

| SKEW Variant | vs trend | vs RSI | vs VIX |
|-|-|-|-|
| skew_z63 | +0.356 | -0.412 | -0.377 |
| skew_z126 | +0.526 | -0.381 | -0.498 |
| skew_pctile | **+0.708** | -0.389 | **-0.626** |
| skew_mom_21d | +0.253 | -0.402 | -0.254 |
| skew_mom_63d | +0.433 | -0.289 | -0.446 |
| skew_level | **+0.716** | -0.282 | **-0.534** |

skew_pctile and skew_level are highly correlated with trend (+0.71) and VIX (-0.63, -0.53). Even the best-performing OOS variants are substantially redundant with existing signals.

## Bonferroni Assessment

Threshold: 0.05 / 8 = 0.00625

- **IS:** NO variant passes Bonferroni for any forward return. Best is skew_pctile vs port_fwd_21d at p=0.012 (FAIL).
- **OOS:** skew_pctile and skew_level pass for fwd_21d and port_fwd_21d, BUT they failed IS. A signal that fails IS but passes OOS does not constitute a valid discovery, it indicates regime dependence or data mining.

## Caveats and Risks

1. **Sign instability across regimes and IS/OOS splits** is the most damaging finding. A signal whose direction depends on market conditions cannot be reliably implemented without a separate regime detection layer, adding complexity and another source of overfitting.

2. **Non-linear relationship** (humped quintile pattern) means a simple linear signal weight would be suboptimal. Capturing the non-linearity requires binning or polynomial transformation, which adds degrees of freedom.

3. **High transaction costs** (6%+ annually even at 5bps) would consume any marginal alpha.

4. **SKEW index methodology changes.** CBOE has updated the SKEW calculation methodology over time, introducing non-stationarity.

5. **High correlation with existing signals.** The best-performing variants (skew_level, skew_pctile) are 0.63-0.72 correlated with trend/VIX, suggesting little marginal information.

## Conclusion

**REJECT**

The CBOE SKEW index does not provide a reliable trading signal for our universe. The fundamental problems are:

1. No signal variant shows consistent IS AND OOS significance
2. Sign flips between regimes (bull vs bear) and between IS/OOS periods
3. Non-monotonic quintile spreads (humped pattern, not linear)
4. Best ICIR is -0.64, well below the |1.0| threshold for a compelling signal
5. High correlation with existing signals (0.63-0.72 for the strongest OOS variants)
6. Prohibitive transaction costs at any reasonable cost assumption

The contrarian hypothesis (high SKEW = bullish) is not supported by the data across the full sample. The regime-dependent behavior (bullish in low-VIX, bearish in bear markets) is interesting but the sample sizes are insufficient for reliable implementation, and the additional regime-conditioning complexity would create overfitting risk.
