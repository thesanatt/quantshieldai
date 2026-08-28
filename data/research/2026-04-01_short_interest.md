# Short Interest Signal Research

**Date:** 2026-04-01
**Signal:** Short interest ratio as equity return predictor

## Signal Description and Hypotheses

Short interest measures the total shares sold short as a percentage of float or average daily volume (days-to-cover). Two competing hypotheses:

**Hypothesis A (Squeeze/contrarian):** High short interest creates squeeze potential. When shorts must cover, buying pressure drives prices higher. Therefore high SI = bullish.

**Hypothesis B (Informed bearishness):** Short sellers are sophisticated informed traders. High SI reflects genuine negative information about a stock. Therefore high SI = bearish.

## Data Availability Assessment

### yfinance Short Interest Fields

| Ticker | Shares Short | Short % Float | Short Ratio (DTC) | Short % Out |
|-|-|-|-|-|
| VOO | N/A | N/A | N/A | N/A |
| AAPL | 124.2M | 0.85% | 3.17 | 0.88% |
| GOOGL | 80.0M | 1.37% | 2.64 | 0.63% |
| AMZN | 84.8M | 0.87% | 1.82 | 0.79% |
| NVDA | 229.2M | 0.98% | 1.28 | 0.94% |
| JNJ | 23.3M | 1.08% | 2.67 | 0.97% |
| KO | 53.7M | 1.26% | 3.17 | 1.25% |
| BRK-B | 11.7M | 0.95% | 2.71 | 0.54% |
| COST | 6.3M | 1.42% | 3.39 | 1.42% |
| MSFT | 79.8M | 1.08% | 2.50 | 1.08% |

### Critical Data Gap

**yfinance provides only CURRENT short interest snapshots, not historical time series.** There is no `ticker.short_interest` historical endpoint. The `get_shares_full()` method returns shares outstanding (not short interest). Historical price data columns (Open, High, Low, Close, Volume) do not include short interest.

**This means we CANNOT run a proper backtested signal analysis.** We have exactly ONE cross-sectional observation (today's snapshot) across 9 stocks (VOO excluded as ETF). This is n=9, which is statistically meaningless.

### Cross-Sectional Analysis (Point-in-Time, n=9)

| Metric | Value |
|-|-|
| SI % Float vs 1-month return | Spearman = -0.30, p = 0.431 |
| SI % Float vs 3-month return | Spearman = +0.30, p = 0.431 |

With n=9, even a Spearman of +/-0.30 produces p > 0.4. No statistical inference is possible.

### Observations on Current SI Levels

All 9 stocks have remarkably LOW short interest (0.85% to 1.42% of float). This is consistent with a low-conviction short-selling environment in mega-cap names. The narrow range (57bp spread from min to max) means there is almost no cross-sectional dispersion to exploit even if we had historical data.

## Proxy Signal: Unusual Volume (Short Squeeze Indicator)

Given the data gap, I tested an unusual volume z-score as a proxy for short-squeeze activity. The logic: abnormal volume spikes may reflect short covering events.

**Signal:** 63-day z-score of the volume-to-20d-average-volume ratio, averaged across all 10 portfolio stocks.

### IC Analysis

| Dataset | vs fwd_5d Spearman (p) | vs fwd_21d Spearman (p) |
|-|-|-|
| IS (n=988) | +0.033 (0.306) | +0.040 (0.206) |
| OOS (n=424) | -0.022 (0.655) | +0.034 (0.491) |

**All p-values > 0.2.** The volume proxy has zero predictive power for forward returns.

### Rolling IC

Volume proxy vs fwd_21d: mean IC = +0.091, std = 0.219, ICIR = +0.42

ICIR of 0.42 is borderline but the static IC is near-zero with no significance, so the rolling ICIR is misleading (likely driven by a few outlier windows).

### Quintile Analysis (Volume Proxy vs fwd_21d)

| Quintile | Mean Return | Std Dev | Count | Sharpe |
|-|-|-|-|-|
| Q1 (low volume) | +1.15% | 4.61% | 283 | +0.86 |
| Q2 | +1.17% | 3.84% | 282 | +1.05 |
| Q3 | +1.04% | 4.17% | 282 | +0.86 |
| Q4 | +1.38% | 3.77% | 282 | +1.26 |
| Q5 (high volume) | +1.66% | 4.33% | 283 | +1.33 |

Weak positive monotonicity (Q5 > Q1 by 51bp per 21 days) but the spread is small and not statistically significant.

### Regime Analysis (Volume Proxy)

| Regime | Spearman | p-value |
|-|-|-|
| High VIX (n=706) | +0.018 | 0.628 |
| Low VIX (n=706) | +0.046 | 0.223 |
| Bull (n=1156) | +0.085 | 0.004 |
| Bear (n=211) | -0.098 | 0.157 |

Marginal significance only in bull markets (p=0.004), but this does not survive Bonferroni correction across regimes.

### Correlation with Existing Signals

| Pair | Correlation |
|-|-|
| volume_proxy vs trend | -0.049 |
| volume_proxy vs VIX | +0.169 |

Low correlations suggest the volume proxy is at least orthogonal, but orthogonality is worthless when the signal itself has no predictive power.

## Bonferroni Assessment

Threshold: 0.05 / 8 = 0.00625

- **Short interest (cross-sectional):** n=9, all p > 0.4. FAIL.
- **Volume proxy IS:** All p > 0.2. FAIL.
- **Volume proxy OOS:** All p > 0.4. FAIL.

No test passes even nominal significance, let alone Bonferroni-corrected significance.

## Transaction Cost Analysis

Not applicable. No tradeable signal exists to assess transaction costs against.

## Caveats and Risks

1. **Fundamental data limitation.** The primary failure mode is data availability, not signal theory. Short interest IS a well-documented factor in academic literature (Rapach, Ringgenberg & Zhou 2016; Desai et al. 2002). Our inability to access historical short interest time series via yfinance prevents testing this thoroughly.

2. **Universe bias.** Our 10-ticker universe consists entirely of mega-cap names with uniformly low short interest (all < 1.5%). Short interest signals are most powerful in small/mid-cap stocks with high short interest (5%+), which our universe excludes by construction.

3. **Alternative data sources exist.** FINRA publishes short interest bi-monthly. Ortex, S3 Partners, and IHS Markit provide daily estimated short interest. These would require paid API access but would enable proper backtesting.

4. **Volume proxy is a poor substitute.** Unusual volume can result from many factors (earnings, news, index rebalancing, options expiry) unrelated to short covering. The proxy conflates too many signals.

## Conclusion

**REJECT**

Short interest cannot be evaluated as a signal in our system due to two insurmountable problems:

1. **No historical time series available** through yfinance. We have exactly one cross-sectional snapshot (n=9), which cannot support statistical inference.

2. **Universe mismatch.** Our mega-cap universe has uniformly low short interest with minimal dispersion. The short interest factor is documented to work primarily in high-SI small/mid-cap stocks, which we do not hold.

The volume-based proxy showed zero predictive power across all tests (no IS or OOS significance, no Bonferroni survival, weak quintile spreads).

**If short interest data becomes available** (e.g., via Ortex API or FINRA scraping), this signal should be re-evaluated. The academic evidence for short interest as a predictor is strong, but we cannot access the necessary data with our current infrastructure. This is a data gap, not a theoretical rejection.
