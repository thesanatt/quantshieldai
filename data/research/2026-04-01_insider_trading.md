# Insider Trading Signal Research

**Date:** 2026-04-01
**Signal:** Corporate insider buying/selling as a predictive signal for forward equity returns

## Signal Description and Hypothesis

Corporate insiders (executives, directors) are required to disclose their stock transactions via SEC Form 4 filings. Academic literature (Lakonishok & Lee 2001, Jeng et al. 2003) suggests insider purchases are informative, insiders buy when they believe their stock is undervalued. Insider selling is noisier (insiders sell for many non-informative reasons: diversification, taxes, liquidity).

**Hypothesis:** Aggregate insider buying/selling activity predicts forward stock returns. Net buying (purchases minus sales) is bullish; heavy selling is bearish.

## Data

- **Source:** yfinance Ticker.insider_transactions
- **Tickers:** AAPL, GOOGL, AMZN, NVDA, JNJ, KO, BRK-B, COST, MSFT (9 stocks; VOO is an ETF with no insider data)
- **Total records:** 801 insider transactions
- **Period:** 2024-04-02 to 2026-03-27 (approximately 2 years)
- **Aligned monthly observations:** 23 months

### Transaction Classification

| Type | Count | % |
|-|-|-|
| Sale | 413 | 51.6% |
| Other (grants, exercises) | 286 | 35.7% |
| Gift | 96 | 12.0% |
| Purchase | 6 | 0.7% |

**Critical observation:** Only 6 purchases across 9 major stocks over 2 years. The data is overwhelmingly dominated by sales. For large-cap tech/blue-chip stocks, insider BUYING is extremely rare. This fundamentally undermines the signal's usefulness for our universe.

## Methodology

1. Classified transactions as sale/purchase/gift/other based on text description and value fields
2. Aggregated to monthly frequency: net_buy = #purchases - #sales per month
3. Tested correlation with 1-month forward SPY returns (market-level) and individual stock returns
4. In-sample: first 70% (16 months), Out-of-sample: last 7 months

## Aggregate Market-Level Results

### In-Sample (16 months)

| Signal | Forward Return | Spearman | Pearson IC | t-stat | p-value |
|-|-|-|-|-|-|
| net_buy | spy_fwd_1m | +0.2386 | +0.3069 | +0.92 | 0.3735 |
| n_sales | spy_fwd_1m | -0.2140 | -0.2930 | -0.82 | 0.4261 |
| sale_value | spy_fwd_1m | -0.0735 | -0.1618 | -0.28 | 0.7867 |

### Out-of-Sample (7 months)

| Signal | Forward Return | Spearman | Pearson IC | t-stat | p-value |
|-|-|-|-|-|-|
| net_buy | spy_fwd_1m | -0.1429 | +0.3762 | -0.32 | 0.7599 |
| n_sales | spy_fwd_1m | +0.1429 | -0.4047 | +0.32 | 0.7599 |
| sale_value | spy_fwd_1m | +0.6786 | +0.4420 | +2.07 | 0.0938 |

**Key finding:** No statistically significant relationships. All p-values are well above 0.05 (ranging from 0.09 to 0.79). The sample sizes are tiny (16 IS, 7 OOS), making any statistical test unreliable. The sale_value OOS result (p=0.09) is based on only 7 observations and is not credible. The Spearman and Pearson correlations even flip signs between IS and OOS for net_buy, indicating instability.

## Per-Ticker Cross-Sectional Results

Testing whether a stock's own insider activity predicts its forward returns:

| Ticker | n (months) | Spearman | p-value |
|-|-|-|-|
| AAPL | 12 | -0.5074 | 0.0922 |
| GOOGL | 14 | -0.1790 | 0.5403 |
| AMZN | 16 | +0.3262 | 0.2176 |
| NVDA | 17 | -0.1855 | 0.4759 |
| JNJ | 11 | +0.3017 | 0.3673 |
| KO | 12 | +0.1371 | 0.6710 |
| COST | 15 | -0.1735 | 0.5363 |
| MSFT | 14 | +0.1247 | 0.6710 |

**Average cross-ticker Spearman: -0.0195** (essentially zero)

**Key finding:** No ticker shows significance at the 5% level. AAPL comes closest (p=0.09) with a NEGATIVE correlation, more insider activity (which is almost entirely sales) correlates with LOWER forward returns. But this is not significant and the sample is tiny (12 months).

The signs are inconsistent across tickers (4 positive, 4 negative), indicating no systematic relationship.

## Regime Analysis

Not performed. With only 23 monthly observations, splitting by regime would produce groups too small for any statistical inference.

## Transaction Cost Sensitivity

Not meaningfully analyzable. If we could construct a tradeable signal, it would change at most monthly (the data granularity), yielding 12 trades/year. At 5bps each way, this is only 0.12%/year, costs would be negligible IF the signal worked. But the signal does not work.

## Fundamental Problems

1. **Insufficient data:** Only 23 months of insider transactions available via yfinance. Academic studies use 10-20+ years of SEC EDGAR filings. Our sample is statistically useless for rigorous inference.

2. **No purchases:** Only 6 insider purchases across 9 large-cap stocks in 2 years. The academic finding that insider BUYING is informative cannot be tested because there are effectively no buys. Large-cap insiders are almost exclusively sellers (diversification, compensation liquidation).

3. **Wrong universe:** The insider trading signal is historically most effective for small-cap stocks where information asymmetry is highest. Our universe (AAPL, MSFT, NVDA, AMZN, etc.) consists of the most-followed, most-analyzed companies in the world. Insiders at these companies have minimal informational edge over the market.

4. **Transaction type ambiguity:** The yfinance data has an empty "Transaction" field for all records. We must infer buy/sell from the "Text" field, which is unreliable (35.7% classified as "other" due to missing text). Option exercises, RSU vestings, and 10b5-1 plan sales are mixed in and are NOT informative.

5. **Monthly aggregation too coarse:** Academic studies typically use event-based analysis (returns around the filing date). Our monthly aggregation destroys the timing information that makes insider signals work.

## Comparison with Academic Literature

The academic literature finds:
- **Insider purchases** earn ~6% annualized alpha (Lakonishok & Lee, 2001), but we have 6 purchases total
- Effect is concentrated in **small caps**, our universe is large cap
- Effect is strongest in the **first few days** after filing, our monthly aggregation misses this
- Signal requires **SEC EDGAR Form 4 data** with precise filing dates, yfinance provides limited historical data

Our null result is entirely consistent with using the wrong data source, wrong universe, and wrong methodology for this signal class.

## Conclusion and Recommendation

**REJECT**

The insider trading signal fails for our use case on multiple levels:

1. **Data inadequacy:** yfinance provides only ~2 years of insider data with poor transaction classification. A proper test requires SEC EDGAR Form 4 filings with 10+ years of history.

2. **Universe mismatch:** Large-cap stocks have minimal insider information asymmetry. The signal is theoretically strongest for small/mid-caps.

3. **No statistical significance:** Zero tests achieve p < 0.05 at either the aggregate or per-ticker level.

4. **Near-zero average correlation:** Cross-ticker average Spearman of -0.02 is indistinguishable from noise.

**If revisiting:** Would require (a) SEC EDGAR Form 4 data with 10+ years of history, (b) expanding the universe to small/mid-cap stocks, (c) event-based methodology (day of filing + subsequent 5/21 day returns), and (d) proper classification of informative vs. non-informative transactions.

**Do NOT integrate into the engine.** There is no alpha here for our universe and data source.
