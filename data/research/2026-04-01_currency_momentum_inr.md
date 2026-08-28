# INR Currency Momentum Signal Research

**Date:** 2026-04-01
**Status:** FAIL, No incremental alpha over existing engine

## Hypothesis

Trending rupee weakness (USDINR rising) predicts differential sector returns in India. IT exporters (TCS, INFY, WIPRO, HCLTECH) benefit from weak rupee; importers/consumers (HINDUNILVR, ITC, TITAN, MARUTI) suffer.

## Data

- **USDINR=X:** 1,299 trading days (2021-04-02 to 2026-04-01)
- **EURINR=X, GBPINR=X:** Same range, used for cross-currency confirmation
- **India VIX (^INDIAVIX):** 1,222 days
- **Nifty 50 (^NSEI):** 1,234 days
- **Stocks:** 4 exporters (TCS, INFY, WIPRO, HCLTECH), 4 importers (HINDUNILVR, ITC, TITAN, MARUTI)
- **Common intersection:** 1,229 days
- **IS/OOS split:** 70/30 (IS: 2021-04-05 to 2024-09-25, 860 days; OOS: 2024-09-26 to 2026-03-30, 369 days)

## Signal Variants

1. `usdinr_mom_21d`, 21-day USDINR return
2. `usdinr_mom_63d`, 63-day USDINR return
3. `usdinr_z_63d`, 63-day z-score of USDINR level

## Results

### 1. Signal-to-Nifty IC

| Signal | Horizon | Split | Spearman | p-value | Pearson | p-value |
|-|-|-|-|-|-|-|
| usdinr_mom_21d | 5d | IS | 0.0238 | 0.4906 | 0.0794 | 0.0215 |
| usdinr_mom_21d | 5d | OOS | 0.0495 | 0.3468 | -0.0189 | 0.7194 |
| usdinr_mom_21d | 21d | IS | 0.0586 | 0.0898 | 0.1308 | 0.0001 |
| usdinr_mom_21d | 21d | OOS | **-0.1456** | **0.0065** | -0.1693 | 0.0015 |
| usdinr_z_63d | 21d | IS | **0.1352** | **0.0001** | 0.1666 | 0.0000 |
| usdinr_z_63d | 21d | OOS | **-0.2189** | **0.0000** | -0.2415 | 0.0000 |

**Critical finding:** The z-score signal shows IS Spearman = +0.1352 (positive, significant) but OOS Spearman = -0.2189 (negative, highly significant). The sign FLIPS between IS and OOS. This is a textbook regime change / overfitting indicator.

### 2. Cross-Sectional IC (Exporter-Importer Spread)

| Signal | Horizon | Split | IC Mean | ICIR | t-stat |
|-|-|-|-|-|-|
| usdinr_mom_21d | 21d | IS | 0.0727 | 0.073 | 2.11 |
| usdinr_mom_21d | 21d | OOS | -0.1839 | -0.187 | -3.49 |

Again the sign reverses OOS. The hypothesis that weak rupee helps exporters relative to importers does not hold consistently.

### 3. Rolling 63-Day IC

| Signal | Mean IC | Std IC | ICIR | % Positive |
|-|-|-|-|-|
| usdinr_mom_21d | 0.0984 | 0.409 | 0.241 | 100% |
| usdinr_mom_63d | 0.1562 | 0.403 | 0.388 | 100% |
| usdinr_z_63d | 0.1305 | 0.407 | 0.321 | 100% |

ICIR below 0.5 for all variants. Below the 0.5 threshold for a tradeable signal.

### 4. Quintile Analysis (usdinr_mom_21d -> Nifty 21d)

**IS:**
| Quintile | Mean Return | Std | Ann SR |
|-|-|-|-|
| Q1 (strong INR) | 0.639% | 3.93% | 0.56 |
| Q3 | 1.767% | 3.50% | 1.75 |
| Q5 (weak INR) | 1.962% | 4.68% | 1.45 |

**OOS:**
| Quintile | Mean Return | Std | Ann SR |
|-|-|-|-|
| Q1 (strong INR) | 1.400% | 4.34% | 1.12 |
| Q3 | -1.158% | 3.48% | -1.15 |
| Q5 (weak INR) | -0.305% | 2.19% | -0.48 |

IS shows weak monotonicity (Q5 > Q1). OOS completely reverses: Q1 now has the best returns. No stable monotonic relationship.

### 5. Exporter-Importer Spread

Spread quintile analysis shows NO consistent pattern IS. OOS, Q5 (weak INR) produces the WORST exporter-importer spread (-3.424%), directly contradicting the hypothesis that weak rupee helps exporters.

Key OOS results:
- usdinr_mom_21d vs spread: Spearman = -0.1697 (p=0.0015), **wrong sign**
- usdinr_mom_63d vs spread: Spearman = -0.2957 (p=0.0000), **wrong sign, highly significant**

The signal is statistically significant OOS but **in the opposite direction** of the hypothesis.

### 6. India VIX Regime Conditioning

| Regime | Spearman (vs Nifty 21d) | p-value |
|-|-|-|
| High VIX (>14.3) | 0.0905 | 0.0302 |
| Low VIX (<=14.3) | -0.1596 | 0.0001 |

Regime-dependent sign flip. In calm markets, rupee weakness is associated with negative Nifty returns (contradicting a simple momentum story). In volatile markets, a weak positive relationship exists but is barely significant.

Neither regime produces a signal with exporter-importer spread (p > 0.37 for both).

### 7. Transaction Cost Impact

Gross mean spread for top-40% USDINR momentum: -1.510% per 21d period
Annualized gross: -18.12%
Annualized net (15bps TC): -18.46%

The strategy LOSES money before and after costs.

### 8. Cross-Currency Confirmation

- EURINR 21d mom vs Nifty 21d: Spearman = 0.0486 (p=0.094), not significant
- GBPINR 21d mom vs Nifty 21d: Spearman = 0.0654 (p=0.024), marginally significant
- Multi-pair consensus (both USDINR and EURINR weakening) produces LOWER forward returns (0.527%) than no-consensus periods (1.129%)

Cross-currency confirmation contradicts the hypothesis.

### 9. Correlation with Existing Engine (UUP)

USDINR_mom_21d vs UUP_mom_21d: Pearson = 0.4403 (p=0.0000)

Moderate correlation. The existing engine already captures ~44% of USDINR momentum variation through UUP.

### 10. Incremental Value After Residualization

After regressing out UUP's contribution:
- USDINR incremental IC: Spearman = -0.0266 (p=0.367)
- **NOT SIGNIFICANT** at any reasonable alpha level

The USDINR signal adds zero incremental information beyond what UUP already provides to the engine.

### 11. Bonferroni Correction (14 signals tested)

Corrected alpha: 0.05 / 14 = 0.0036

6 results survive Bonferroni correction, but ALL of them either (a) have the wrong sign OOS or (b) show IS/OOS sign reversal. Statistical significance in the wrong direction is worse than no significance at all.

## Failure Modes Identified

1. **IS/OOS sign reversal:** The most damning finding. Every signal variant that shows significance in IS reverses sign in OOS. This is either a regime change (RBI policy shifted in late 2024) or pure IS overfit.

2. **Hypothesis falsified OOS:** Weak rupee does NOT help exporters relative to importers in the OOS period. The spread goes the WRONG way with high significance.

3. **No incremental value:** After controlling for UUP (already in the engine), USDINR adds nothing (Spearman = -0.027, p = 0.37).

4. **Negative expected returns:** The long-exporters/short-importers-when-rupee-weak strategy has annualized returns of -18%.

5. **ICIR below threshold:** Best ICIR = 0.388 (usdinr_mom_63d), well below the 0.5 minimum for a tradeable signal.

## Verdict: FAIL

Do not implement. The INR currency momentum signal:
- Reverses sign between IS and OOS across all variants
- Adds zero incremental alpha over existing UUP proxy
- Falsifies the core exporter/importer hypothesis OOS
- Has negative expected returns after costs
- ICIR well below tradeable threshold

The existing engine's use of UUP as a dollar proxy already captures whatever INR information is relevant for the US equity universe. For India-specific coverage, the signal instability makes it untradeable.
