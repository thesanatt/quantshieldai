# Breadth Indicator Multivariate Analysis

**Date:** 2026-04-01
**Purpose:** Determine if breadth_pct_above_50d and breadth_mom_21d add marginal alpha beyond existing signals (trend, RSI, VIX term structure)

## Background

The breadth indicators study found breadth_pct_above_50d with ICIR of -1.45 and strong OOS performance, but 0.77 correlation with trend and 0.68 with RSI. Review required a multivariate analysis to determine if the signal is genuinely additive or redundant.

## Data

- **Period:** 2021-01-05 to 2026-03-02 (1,294 aligned rows)
- **IS:** 905 rows | **OOS:** 389 rows
- **Existing signals controlled for:** trend (SMA50/SMA200), RSI (14-day), VIX term structure
- **Forward returns tested:** spy_fwd_5d, spy_fwd_21d, port_fwd_5d, port_fwd_21d

## Part 1: Does breadth_pct_above_50d Add Alpha Beyond Existing Signals?

### Multivariate Regression (F-test for marginal contribution)

| Forward Return | Dataset | R2 Existing | R2 +Breadth | Delta R2 | F-stat | p-value | Breadth t-stat | Breadth p-value |
|-|-|-|-|-|-|-|-|-|
| fwd_5d | IS | 0.0010 | 0.0011 | 0.0000 | 0.02 | 0.877 | +0.16 | 0.877 |
| fwd_5d | OOS | 0.0723 | 0.0750 | 0.0027 | 1.13 | 0.288 | +1.06 | 0.288 |
| fwd_21d | IS | 0.0165 | 0.0417 | **0.0253** | **23.74** | **0.000001** | **-4.87** | **0.000001** |
| fwd_21d | OOS | 0.0615 | 0.0616 | 0.0002 | 0.07 | 0.797 | +0.26 | 0.797 |
| port_fwd_5d | IS | 0.0014 | 0.0021 | 0.0007 | 0.59 | 0.443 | -0.77 | 0.443 |
| port_fwd_5d | OOS | 0.0616 | 0.0641 | 0.0026 | 1.05 | 0.307 | +1.02 | 0.307 |
| port_fwd_21d | IS | 0.0228 | 0.0524 | **0.0296** | **28.15** | **0.000000** | **-5.31** | **0.000000** |
| port_fwd_21d | OOS | 0.0826 | 0.0845 | 0.0018 | 0.77 | 0.382 | +0.88 | 0.382 |

**Verdict:** breadth_pct_above_50d is significant in-sample for 21-day returns (t = -4.87, -5.31) but **completely fails out-of-sample** (p = 0.797, 0.382). The IS alpha is entirely absorbed by existing signals in the OOS period.

### Residualized (Marginal) IC

After orthogonalizing breadth_pct_above_50d against existing signals:

| Forward Return | Dataset | Marginal Spearman | p-value | Marginal ICIR |
|-|-|-|-|-|
| fwd_5d | IS | -0.0307 | 0.357 | -0.14 |
| fwd_21d | IS | **-0.1573** | **0.000002** | **-0.63** |
| port_fwd_5d | IS | -0.0652 | 0.050 | -0.24 |
| port_fwd_21d | IS | **-0.1383** | **0.000030** | **-0.42** |
| fwd_5d | OOS | +0.0162 | 0.751 | -0.17 |
| fwd_21d | OOS | -0.0274 | 0.590 | -0.98 |
| port_fwd_5d | OOS | +0.0003 | 0.995 | -0.26 |
| port_fwd_21d | OOS | +0.0182 | 0.721 | -1.05 |

**Verdict:** The marginal IC collapses to near-zero OOS. The ICIR values OOS are misleading because the mean IC is near zero with low variance. The raw ICIR of -1.45 (reported in the breadth indicators study) was almost entirely driven by the overlap with trend and RSI signals.

### Key Finding for breadth_pct_above_50d

The signal's IS marginal ICIR drops from raw -1.45 to residualized -0.63 (57% reduction), confirming massive redundancy. OOS, the residualized signal is completely dead (Spearman near zero, all p > 0.5). **The signal is redundant with existing trend and RSI signals.**

## Part 2: Does breadth_mom_21d Add Alpha?

### Multivariate Regression

| Forward Return | Dataset | Delta R2 | F-stat | p-value | t-stat | p-value |
|-|-|-|-|-|-|-|
| fwd_5d | IS | 0.0069 | 6.29 | 0.012 | -2.51 | 0.012 |
| fwd_5d | OOS | 0.0048 | 2.01 | 0.157 | -1.42 | 0.157 |
| fwd_21d | IS | 0.0044 | 4.08 | 0.044 | -2.02 | 0.044 |
| fwd_21d | OOS | **0.1463** | **70.91** | **0.000000** | **-8.42** | **0.000000** |
| port_fwd_5d | IS | 0.0040 | 3.58 | 0.059 | -1.89 | 0.059 |
| port_fwd_5d | OOS | 0.0042 | 1.73 | 0.190 | -1.31 | 0.190 |
| port_fwd_21d | IS | 0.0001 | 0.09 | 0.765 | -0.30 | 0.765 |
| port_fwd_21d | OOS | **0.1091** | **51.84** | **0.000000** | **-7.20** | **0.000000** |

### Residualized (Marginal) IC

| Forward Return | Dataset | Marginal Spearman | p-value | Marginal ICIR |
|-|-|-|-|-|
| fwd_5d | IS | -0.0694 | 0.037 | -0.43 |
| fwd_21d | IS | -0.0889 | 0.007 | -0.34 |
| port_fwd_5d | IS | -0.0549 | 0.099 | -0.22 |
| port_fwd_21d | IS | -0.0260 | 0.435 | +0.08 |
| fwd_5d | OOS | -0.0808 | 0.112 | -0.05 |
| fwd_21d | OOS | **-0.4276** | **0.000000** | **-0.99** |
| port_fwd_5d | OOS | -0.0830 | 0.102 | -0.00 |
| port_fwd_21d | OOS | **-0.3716** | **0.000000** | **-0.80** |

**Verdict:** breadth_mom_21d shows the OPPOSITE pattern to breadth_pct_above_50d. Its IS marginal contribution is weak (t = -2.02 for fwd_21d, borderline), but it **dramatically strengthens OOS** (t = -8.42 for fwd_21d, R2 improvement of 14.6%). The marginal OOS Spearman of -0.43 with p < 0.000001 is remarkable.

This OOS strengthening is unusual and warrants caution (possible regime shift or structural break in the OOS period). However, the signal's low correlation with existing signals (VIF = 1.14) means it is genuinely orthogonal.

## Part 3: Combined Model

Full model (trend + RSI + VIX_TS + breadth_pct_50d + breadth_mom_21d) for fwd_21d:

| Variable | IS coef | IS t-stat | IS p-value | OOS coef | OOS t-stat | OOS p-value |
|-|-|-|-|-|-|-|
| intercept | +0.035 | +6.78 | 0.0000 | +0.035 | +4.08 | 0.0001 |
| trend | +0.015 | +3.57 | 0.0004 | -0.025 | -2.39 | 0.0174 |
| rsi | -0.017 | -1.63 | 0.1026 | +0.008 | +0.51 | 0.6138 |
| vix_ts | -0.003 | -1.11 | 0.2668 | +0.005 | +1.77 | 0.0780 |
| breadth_pct_50d | -0.050 | -4.96 | 0.0000 | -0.020 | -1.02 | 0.3078 |
| breadth_mom_21d | -0.176 | -2.22 | 0.0264 | **-0.839** | **-8.48** | **0.0000** |

**OOS R2 = 0.210** (vs 0.062 for existing signals alone, a 3.4x improvement driven entirely by breadth_mom_21d)

## Part 4: Variance Inflation Factors

| Signal | VIF |
|-|-|
| trend | 2.46 |
| rsi | 2.52 |
| vix_ts | 1.64 |
| breadth_pct_above_50d | **4.20** |
| breadth_mom_21d | **1.14** |

VIF of 4.20 for breadth_pct_above_50d confirms high multicollinearity. VIF of 1.14 for breadth_mom_21d confirms near-independence.

## Part 5: Correlation Matrix

|  | trend | rsi | vix_ts | breadth_pct_50d | breadth_mom_21d |
|-|-|-|-|-|-|
| trend | 1.000 | -0.504 | +0.274 | **+0.753** | -0.201 |
| rsi | -0.504 | 1.000 | -0.570 | **-0.735** | +0.350 |
| vix_ts | +0.274 | -0.570 | 1.000 | **+0.542** | -0.169 |
| breadth_pct_50d | +0.753 | -0.735 | +0.542 | 1.000 | -0.286 |
| breadth_mom_21d | -0.201 | +0.350 | -0.169 | -0.286 | 1.000 |

## Caveats

1. **breadth_mom_21d OOS strengthening is suspicious.** A signal that is marginal IS (t = -2.02) but dominant OOS (t = -8.42) raises questions about structural breaks, regime shifts, or look-ahead bias. The OOS period (approximately 2024-2025) may have unusual market conditions (AI bubble, rate cycle) that favor this specific signal.

2. **Overlapping returns.** The 21-day forward return overlap inflates t-statistics. True independent observations are ~1294/21 = 62. Adjusting OOS t-stat of -8.42 by sqrt(21) gives ~1.84, which is marginal.

3. **Short OOS window.** Only 389 rows (~1.5 years) OOS is insufficient for robust conclusions. The signal needs verification across a full market cycle.

4. **Coefficient instability.** The trend signal flips sign between IS (+0.015) and OOS (-0.025), suggesting model instability.

## Conclusions

### breadth_pct_above_50d: REJECT

The signal's impressive raw statistics (ICIR -1.45, Bonferroni-passing OOS p-values) are almost entirely explained by its 0.75/0.74 correlation with existing trend and RSI signals. After controlling for these signals:
- OOS marginal Spearman IC = 0.00 to -0.03 (all p > 0.5)
- OOS R2 improvement = 0.02% to 0.27%
- VIF = 4.20 (high multicollinearity)

**The signal is redundant. It should NOT be added to the engine.**

### breadth_mom_21d: PROMISING (with caveats)

The signal shows genuine orthogonal predictive power:
- Low correlation with all existing signals (max |r| = 0.35, VIF = 1.14)
- Strong OOS marginal contribution (Spearman -0.43, t = -8.42, R2 +14.6%)
- Combined model OOS R2 = 0.21 (3.4x improvement over existing signals alone)

However, the IS-to-OOS strengthening is atypical and raises overfitting concerns in reverse (the OOS period may be unusually favorable). The signal warrants a **trial implementation at low weight (2-3%)** with live monitoring of marginal IC stability.

**Recommended action:** Implement breadth_mom_21d as signal #8 with conservative weight. Reject breadth_pct_above_50d as redundant. Monitor rolling marginal IC for 6 months before increasing weight.

## Review Verdict on breadth_mom_21d: Rejected

The trial-implementation recommendation above was overridden on review. An in-sample delta R2 of 0.0044 (t = -2.02) rising to 0.1463 (t = -8.42) out of sample is a 33x increase in explanatory power on unseen data, which points to a regime-specific artifact in the 2024 to 2025 window rather than a structural relationship. The overlap-adjusted OOS t-statistic is about 1.84 (dividing by sqrt(21)), not significant after Bonferroni. The trend coefficient flips sign between IS (+0.015) and OOS (-0.025), so the combined model is unstable. No rolling-window stability test and no economic mechanism were provided. Neither breadth variant entered the engine.
