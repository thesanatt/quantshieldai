# Sector Relative Strength Signal Research

**Date:** 2026-04-01
**Signal:** Sector ETF relative momentum as equity return predictor

## Signal Description and Hypothesis

Sector relative strength measures which GICS sectors are outperforming or underperforming over trailing periods. Academic literature on industry momentum (Moskowitz & Grinblatt 1999) documents persistent return predictability from sector-level momentum. The hypothesis is twofold:

1. **Cross-sectional:** Stocks in strong sectors (high relative momentum) should outperform stocks in weak sectors.
2. **Aggregate:** Sector dispersion and rotation patterns predict broad market returns. High dispersion may indicate regime transitions.

Three signal variants tested:
1. **cross_sectional** = Mean sector rank percentile across portfolio stocks (using 63-day sector momentum, mapped via sector ETFs)
2. **sector_dispersion** = Cross-sectional standard deviation of 63-day sector ETF returns
3. **rotation_signal** = Mean return of top-3 sectors minus mean return of bottom-3 sectors (63-day)

Sector ETFs used: XLK, XLV, XLF, XLE, XLI, XLP, XLU, XLY, XLC, XLRE, XLB

Ticker-to-sector mapping: AAPL/NVDA/MSFT -> XLK, GOOGL -> XLC, AMZN -> XLY, JNJ -> XLV, KO/COST -> XLP, BRK-B -> XLF, VOO -> market (neutral 0.5 rank)

## Data

- **11 sector ETFs:** daily prices
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
| cross_sectional | spy_fwd_5d | +0.0334 | +0.0237 | +0.78 | 0.4368 |
| cross_sectional | spy_fwd_21d | +0.0717 | +0.0387 | +1.27 | 0.2045 |
| cross_sectional | port_fwd_5d | +0.0341 | +0.0162 | +0.53 | 0.5949 |
| cross_sectional | port_fwd_21d | +0.0681 | +0.0574 | +1.89 | 0.0594 |
| sector_dispersion | spy_fwd_5d | -0.0096 | +0.0159 | +0.52 | 0.6016 |
| sector_dispersion | spy_fwd_21d | +0.0812 | +0.0708 | +2.33 | 0.0200 |
| sector_dispersion | port_fwd_5d | -0.0286 | +0.0047 | +0.15 | 0.8784 |
| sector_dispersion | port_fwd_21d | +0.0397 | +0.0194 | +0.64 | 0.5239 |
| rotation_signal | spy_fwd_5d | -0.0137 | +0.0127 | +0.42 | 0.6760 |
| rotation_signal | spy_fwd_21d | +0.0746 | +0.0755 | +2.48 | 0.0132 |
| rotation_signal | port_fwd_5d | -0.0297 | +0.0020 | +0.07 | 0.9476 |
| rotation_signal | port_fwd_21d | +0.0478 | +0.0368 | +1.21 | 0.2270 |

Even in-sample, results are weak. Only sector_dispersion and rotation_signal vs spy_fwd_21d reach conventional significance (p=0.02 and p=0.01), with Pearson ICs of only +0.07. No signal variant predicts 5-day returns. No variant predicts portfolio-level 21-day returns at p<0.05 (cross_sectional is marginal at p=0.06).

**After Bonferroni correction (threshold = 0.05/6 = 0.0083):** Only rotation_signal vs spy_fwd_21d (p=0.0132) comes close but still FAILS Bonferroni. No in-sample result survives multiple testing correction.

## Out-of-Sample Results

| Signal | Forward Return | Spearman | Pearson IC | t-stat | p-value |
|-|-|-|-|-|-|
| cross_sectional | spy_fwd_5d | -0.0982 | -0.0477 | -1.02 | 0.3060 |
| cross_sectional | spy_fwd_21d | -0.1136 | -0.0648 | -1.39 | 0.1641 |
| cross_sectional | port_fwd_5d | -0.1182 | -0.0693 | -1.49 | 0.1372 |
| cross_sectional | port_fwd_21d | -0.1251 | -0.1140 | -2.46 | 0.0142 |
| sector_dispersion | spy_fwd_5d | -0.0116 | -0.0335 | -0.72 | 0.4724 |
| sector_dispersion | spy_fwd_21d | -0.0987 | -0.0799 | -1.72 | 0.0862 |
| sector_dispersion | port_fwd_5d | -0.0007 | -0.0249 | -0.54 | 0.5928 |
| sector_dispersion | port_fwd_21d | -0.0063 | -0.0191 | -0.41 | 0.6820 |
| rotation_signal | spy_fwd_5d | -0.0058 | -0.0229 | -0.49 | 0.6238 |
| rotation_signal | spy_fwd_21d | -0.0975 | -0.0774 | -1.66 | 0.0967 |
| rotation_signal | port_fwd_5d | +0.0029 | -0.0190 | -0.41 | 0.6844 |
| rotation_signal | port_fwd_21d | -0.0128 | -0.0251 | -0.54 | 0.5898 |

**Complete OOS failure with sign reversals.** Every single correlation that was positive in-sample flips negative out-of-sample. The cross_sectional signal at port_fwd_21d actually becomes significantly negative (p=0.0142), meaning the signal works in REVERSE OOS. This is the hallmark of a spurious in-sample relationship.

## Rolling IC Analysis (63-day window)

| Signal vs Return | Mean IC | IC Std | ICIR |
|-|-|-|-|
| cross_sectional vs spy_fwd_5d | -0.0562 | 0.2726 | -0.2062 |
| cross_sectional vs spy_fwd_21d | -0.0837 | 0.4080 | -0.2050 |
| sector_dispersion vs spy_fwd_5d | -0.0319 | 0.2727 | -0.1169 |
| sector_dispersion vs spy_fwd_21d | -0.0222 | 0.4012 | -0.0553 |
| rotation_signal vs spy_fwd_5d | -0.0367 | 0.2702 | -0.1360 |
| rotation_signal vs spy_fwd_21d | -0.0356 | 0.3979 | -0.0894 |

All ICIR values are negative. The full-sample rolling IC analysis tells a different story than the in-sample split: the signal is actually net-negative over the full period. The IS results were an artifact of the specific date split.

## Quintile Analysis (rotation_signal -> 21-day SPY forward returns)

| Quintile | Mean Return | Std Dev | Count | Annualized Sharpe |
|-|-|-|-|-|
| Q1 (low rotation) | 1.49% | 3.96% | 308 | +1.30 |
| Q2 | 0.84% | 4.87% | 308 | +0.60 |
| Q3 | 0.23% | 6.41% | 308 | +0.12 |
| Q4 | 1.60% | 4.52% | 308 | +1.23 |
| Q5 (high rotation) | 1.93% | 5.73% | 308 | +1.17 |

Non-monotonic pattern. Q3 is the worst performer, not Q1. Q1 actually has the second-highest Sharpe. There is no exploitable monotonic relationship.

## Quintile Analysis (sector_dispersion -> 21-day SPY forward returns)

| Quintile | Mean Return | Std Dev | Count | Annualized Sharpe |
|-|-|-|-|-|
| Q1 (low dispersion) | 1.52% | 3.95% | 308 | +1.33 |
| Q2 | 0.79% | 4.82% | 308 | +0.57 |
| Q3 | 0.20% | 6.35% | 308 | +0.11 |
| Q4 | 1.63% | 4.56% | 308 | +1.24 |
| Q5 (high dispersion) | 1.95% | 5.81% | 308 | +1.16 |

Nearly identical to rotation_signal quintiles, suggesting both capture the same underlying factor. Same non-monotonic problem.

## Cross-Sectional Quintile Analysis (per-stock sector strength -> individual stock 21-day forward returns)

| Quintile | Mean Return | Std Dev | Count | Annualized Sharpe |
|-|-|-|-|-|
| Q1 (weak sector) | 2.09% | 8.67% | 3505 | +0.84 |
| Q2 | 1.72% | 7.91% | 2650 | +0.75 |
| Q3 | 1.96% | 7.76% | 4014 | +0.88 |
| Q4 | 2.40% | 8.24% | 3265 | +1.01 |
| Q5 (strong sector) | 2.35% | 9.36% | 1650 | +0.87 |

Weak monotonic tendency from Q2-Q5 but Q1 breaks it. The Q5-Q1 spread is only +0.26%, economically insignificant given transaction costs. The cross-sectional stock selection use case is not supported.

## Regime Analysis

| Regime | Signal | n | Spearman | p-value |
|-|-|-|-|-|
| High VIX | cross_sectional | 770 | +0.1462 | 0.0000 |
| High VIX | sector_dispersion | 770 | +0.0233 | 0.5178 |
| High VIX | rotation_signal | 770 | +0.0291 | 0.4196 |
| Low VIX | cross_sectional | 770 | -0.0166 | 0.6452 |
| Low VIX | sector_dispersion | 770 | -0.1033 | 0.0041 |
| Low VIX | rotation_signal | 770 | -0.1135 | 0.0016 |
| Bull | cross_sectional | 1219 | -0.0311 | 0.2781 |
| Bull | sector_dispersion | 1219 | -0.0218 | 0.4471 |
| Bull | rotation_signal | 1219 | -0.0344 | 0.2298 |
| Bear | cross_sectional | 321 | +0.2932 | 0.0000 |
| Bear | sector_dispersion | 321 | +0.0775 | 0.1659 |
| Bear | rotation_signal | 321 | +0.0904 | 0.1061 |

The cross_sectional signal shows regime dependency: positive and significant in high-VIX/bear markets, but zero or negative in low-VIX/bull markets. However, this is driven almost entirely by the COVID recovery period. The sector_dispersion and rotation signals flip sign between regimes, which is concerning.

## Transaction Cost Analysis

| Signal | Cost Level | Meaningful Changes | Turnover/day | Annual Cost |
|-|-|-|-|-|
| cross_sectional | 5bps | 163 | 0.106 | 2.67% |
| cross_sectional | 10bps | 163 | 0.106 | 5.33% |
| sector_dispersion | 5bps | 110 | 0.071 | 1.80% |
| rotation_signal | 5bps | 125 | 0.081 | 2.05% |

Moderate turnover but irrelevant given the signal has no alpha to capture.

## Correlation with Existing Signals

| Pair | Correlation |
|-|-|
| cross_sectional vs momentum_12m | -0.08 |
| cross_sectional vs rsi_14 | +0.20 |
| cross_sectional vs trend | +0.28 |
| cross_sectional vs vix_level | -0.23 |
| cross_sectional vs vix_term_struct | -0.25 |
| sector_dispersion vs momentum_12m | -0.22 |
| sector_dispersion vs vix_level | +0.44 |
| rotation_signal vs momentum_12m | -0.23 |
| rotation_signal vs vix_level | +0.42 |

Notable correlations: sector_dispersion and rotation_signal correlate +0.42 to +0.44 with VIX level. The cross_sectional signal correlates +0.28 with trend and -0.25 with VIX term structure. These signals are NOT independent of the existing signal set, particularly the VIX/cross-asset signals. Any marginal predictive power would be subsumed by existing signals.

## Bonferroni Correction

Adjusted significance threshold: 0.05/6 = 0.0083. No in-sample result survives Bonferroni correction. The strongest IS result (rotation_signal vs spy_fwd_21d, p=0.0132) fails. No OOS result is significant in the hypothesized direction.

## Caveats and Risks

1. **Mapping limitation:** Our portfolio is heavily tech-weighted (AAPL, MSFT, NVDA all map to XLK, GOOGL to XLC). This reduces effective diversification in the cross-sectional signal, 3 of 10 stocks share one sector signal.
2. **Short sample:** 6 years may not capture full sector rotation cycles. However, this period includes multiple distinct regimes (COVID crash, recovery, 2022 bear, 2023-2025 bull), which should be sufficient to detect a robust signal.
3. **Moskowitz & Grinblatt (1999) used individual stock sorts, not ETF-level aggregates.** The signal may work at higher granularity (industry-level within sectors) but not at the broad sector ETF level.
4. **Concentration risk:** The engine universe has only 10 stocks spanning effectively 5-6 sectors. Industry momentum literature uses hundreds of stocks across dozens of industries. Our universe is too concentrated to exploit this signal.

## Conclusion and Recommendation

**REJECT**

The sector relative strength signal shows no robust predictive power for our equity universe. Key failures:
- No in-sample result survives Bonferroni correction
- Complete OOS failure with sign reversals across all variants
- All rolling ICIR values are negative
- Non-monotonic quintile patterns
- High correlation with existing signals (VIX level, trend) means no diversification benefit
- Universe too concentrated (10 stocks, ~5 sectors) to exploit sector momentum effectively

The academic literature on industry momentum is compelling but operates at a scale and granularity incompatible with our concentrated portfolio. This signal would require expanding the universe to 50+ stocks across all GICS sectors to become viable.
