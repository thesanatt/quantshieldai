# Put/Call Ratio (Sentiment) Signal Research

**Date:** 2026-04-01
**Signal:** CBOE equity put/call ratio as contrarian sentiment indicator

## Signal Description and Hypothesis

The CBOE equity put/call ratio measures the ratio of put option volume to call option volume. High readings indicate excessive fear (more puts being bought for protection), which contrarian theory suggests is bullish. Low readings indicate complacency, which is bearish.

**Hypothesis:** Extreme put/call readings predict forward equity returns in the opposite direction (contrarian signal).

## Data Availability Problem

**Critical issue:** The CBOE equity put/call ratio (^PCCE, ^PCC) is NOT available via yfinance as a downloadable time series. Attempts to fetch these symbols returned 0 rows. The ticker "PCCE" returned 512 rows but this is a put/call ratio ETN (exchange-traded note), not the raw ratio data. Its price reflects ETN mechanics, not the put/call ratio directly.

**Workaround:** Since direct put/call data is unavailable through our data pipeline (yfinance), I constructed two proxy sentiment indicators from available data:

1. **VIX Percentile Rank** (rolling 252-day), Higher percentile = more fear = contrarian bullish
2. **SKEW Z-Score** (rolling 63-day standardization of CBOE SKEW index), measures tail risk pricing

## Data

- **VIX (^VIX):** 1,256 daily observations
- **SKEW (^SKEW):** 1,215 daily observations
- **SPY:** 1,255 daily observations
- **Period:** 2021-04-01 to 2026-03-31
- **Aligned sample after signal computation:** 943 rows

## Methodology

1. VIX percentile = percentile rank of current VIX within trailing 252-day window
2. SKEW z-score = (SKEW - 63d SMA) / 63d std
3. Forward returns: 5-day and 21-day SPY
4. In-sample: first 70% (660 rows, 2022-04-12 to 2025-01-13)
5. Out-of-sample: last 30% (283 rows, 2025-01-14 to 2026-03-02)

## In-Sample Results

| Signal | Forward Return | Spearman | Pearson IC | t-stat | p-value |
|-|-|-|-|-|-|
| vix_pctile | spy_fwd_5d | +0.0021 | -0.0137 | +0.05 | 0.9576 |
| vix_pctile | spy_fwd_21d | +0.0557 | +0.0478 | +1.43 | 0.1526 |
| skew_z | spy_fwd_5d | -0.0021 | +0.0205 | -0.05 | 0.9575 |
| skew_z | spy_fwd_21d | -0.0451 | -0.0181 | -1.16 | 0.2477 |

**Key finding:** No statistically significant relationships in-sample. All p-values are well above 0.05. The VIX percentile shows a weak positive correlation with 21-day returns (directionally consistent with contrarian hypothesis) but is far from significant (t=1.43, p=0.15).

## Out-of-Sample Results

| Signal | Forward Return | Spearman | Pearson IC | t-stat | p-value |
|-|-|-|-|-|-|
| vix_pctile | spy_fwd_5d | +0.1318 | +0.0711 | +2.23 | 0.0267 |
| vix_pctile | spy_fwd_21d | +0.0074 | +0.0096 | +0.12 | 0.9014 |
| skew_z | spy_fwd_5d | +0.1209 | +0.1099 | +2.04 | 0.0420 |
| skew_z | spy_fwd_21d | +0.1866 | +0.1378 | +3.18 | 0.0016 |

**Key finding:** Some OOS significance appears, but this is suspicious. The signal shows NO in-sample significance but then shows significance OOS. This pattern is more consistent with random variation than a true signal. The OOS period (Jan 2025 - Mar 2026) may have specific market conditions (tariff volatility) that happened to produce this correlation.

## Quintile Analysis (vix_pctile -> 21-day SPY forward returns)

| Quintile | Mean Return | Std Dev | Count | Annualized Sharpe |
|-|-|-|-|-|
| Q1 (calm) | 1.46% | 3.18% | 189 | 1.59 |
| Q2 | 1.60% | 3.38% | 188 | 1.64 |
| Q3 | 0.36% | 4.13% | 190 | 0.30 |
| Q4 | 0.45% | 5.31% | 188 | 0.29 |
| Q5 (fear) | 2.32% | 5.12% | 188 | 1.57 |

**Key finding:** The quintile pattern is NOT monotonic. Q1 (calm) and Q2 actually have high returns, undermining the contrarian thesis. Q5 (fear) does show high returns, but so do the calm quintiles. The middle quintiles (Q3-Q4) have the worst returns. This non-monotonic pattern suggests the signal lacks a clean, tradeable relationship.

## Regime Analysis

| Regime | n | Spearman | p-value |
|-|-|-|-|
| Bull (SPY > SMA200) | 694 | -0.0069 | 0.8562 |
| Bear (SPY <= SMA200) | 50 | +0.1125 | 0.4366 |

**Key finding:** No significant relationship in either regime. The bear market sample is very small (n=50) making it unreliable. In bull markets, the correlation is essentially zero.

## Extreme Fear Analysis

- **Extreme fear frequency (VIX > 80th percentile):** 19.2% of days
- **Average 21-day forward return in extreme fear:** +2.35%
- **Average 21-day forward return otherwise:** +0.97%
- **Spread:** +1.38%

The extreme fear spread exists but is modest and not statistically robust given the high variance of returns during fear periods.

## Transaction Cost Sensitivity

- **Extreme fear transitions:** 72 in 943 days = 0.076/day
- **At 5bps each way:** 0.96%/year
- **At 10bps each way:** 1.92%/year
- **At 20bps each way:** 3.85%/year

Higher turnover than the VIX term structure signal, and with a weaker alpha, costs eat significantly more into the potential edge.

## Caveats and Limitations

1. **Proxy problem:** We could not obtain actual CBOE put/call ratio data. The VIX percentile rank is a crude proxy at best, it captures volatility level, not options market positioning directly. A proper test requires actual put/call ratio data from CBOE or a paid data provider.

2. **Non-monotonic quintile pattern:** Fatal for a clean trading signal. The relationship is not directionally consistent across the distribution.

3. **No in-sample significance:** The core statistical tests fail. Any OOS significance may be spurious.

4. **Small bear market sample:** Cannot properly test the signal in the regime where it's theoretically most valuable.

5. **Overlapping returns inflation:** Same caveat as VIX term structure, effective independent sample is much smaller than the raw count.

## Conclusion and Recommendation

**REJECT (with caveat)**

The put/call ratio hypothesis cannot be properly tested with available data. The VIX percentile proxy shows:
- No in-sample statistical significance
- Non-monotonic quintile returns (fatal for a trading signal)
- No significance across market regimes
- Higher transaction costs relative to potential alpha

**However**, this is a test of a proxy, not the actual signal. The actual CBOE put/call ratio might behave differently. If a paid data source for CBOE put/call ratio data becomes available, this hypothesis should be re-tested.

**If integrating:** Do NOT add based on current evidence. The VIX term structure signal (separate research) already captures the volatility-based sentiment information more effectively.
