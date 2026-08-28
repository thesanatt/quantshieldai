# Survivorship Bias Quantification

**Date:** 2026-04-02
**Signal:** Universe Selection Bias
**Status:** QUANTIFIED

## Signal Description and Hypothesis

**Hypothesis:** Our US and India universes are selected with hindsight knowledge of which stocks survived and thrived. This inflates all backtest metrics, Sharpe ratio, alpha, total return, because we are systematically excluding stocks that were once large-cap but subsequently underperformed or were delisted.

**The core problem:** Selecting AAPL, NVDA, GOOGL, AMZN, MSFT, etc. in a backtest starting 5 years ago implicitly assumes we knew in 2021 that these would be the winners. We did not. An honest 2021 investor would have held some stocks that subsequently cratered.

## Data Used and Time Period

- **Period:** April 2021, April 2026 (5 years)
- **Source:** Yahoo Finance via yfinance
- **Current US Universe (9):** AAPL, GOOGL, AMZN, NVDA, JNJ, KO, BRK-B, COST, MSFT
- **Historical Comparison (9):** AAPL, MSFT, AMZN, GOOGL, BRK-B, JNJ, XOM, WFC, T
  - Rationale: XOM, WFC, T were S&P 500 top-10 by market cap in 2016-2020 era before energy/financials/telecom rotated out
- **Fallen Angels (6):** GE, XOM, WFC, IBM, T, INTC, stocks that were top large-caps 5-10 years ago
- **India Current (20):** Full INDIA_TICKERS from config.py
- **India Fallen (4):** YESBANK, VEDL, ZEEL, INDUSINDBK, former Nifty 50 constituents that underperformed
  - Note: DHFL and TATAMOTORS were delisted/reorganized and could not be downloaded, this itself is survivorship bias evidence

## Methodology

1. Download 5-year daily price data for all tickers
2. Compute equal-weight portfolio returns for: (a) current universe, (b) historical universe, (c) expanded universe (current + fallen angels)
3. Compare Sharpe ratio, annualized return, total return, max drawdown
4. The difference between (a) and (b) is the survivorship bias estimate
5. No lookahead: all returns computed from the same start date, the only difference is which stocks are included

## Results: United States

### Individual 5-Year Annualized Returns

| Ticker | 5Y Ann Return | Status |
|-|-|-|
| NVDA | +66.2% | Current universe (massive outlier) |
| COST | +23.9% | Current universe |
| GOOGL | +22.1% | Current universe |
| AAPL | +15.9% | Current universe |
| BRK-B | +12.8% | Current universe |
| JNJ | +11.5% | Current universe |
| KO | +10.9% | Current universe |
| MSFT | +9.1% | Current universe |
| AMZN | +5.5% | Current universe |
| **GE** | **+35.0%** | **Fallen angel (outperformed!)** |
| **XOM** | **+28.2%** | **Fallen angel (outperformed!)** |
| **WFC** | **+18.1%** | **Fallen angel** |
| **IBM** | **+18.0%** | **Fallen angel** |
| **T** | **+11.1%** | **Fallen angel** |
| **INTC** | **-4.5%** | **Fallen angel (destroyed value)** |
| VOO | +11.6% | Benchmark |

**Critical observation:** GE and XOM, the canonical "fallen angels" that left the S&P 500 top-10, actually outperformed most of our current universe over the last 5 years. The survivorship narrative is more nuanced than expected, some "fallen" stocks recover dramatically. The real damage comes from stocks like INTC (-4.5% annualized) and, for India, ZEEL (-16.9% annualized).

### Portfolio-Level Comparison (5-Year, Equal Weight)

| Portfolio | Sharpe | Ann Return | Ann Vol | 5Y Total | Max DD |
|-|-|-|-|-|-|
| **Current 9 (our universe)** | **1.154** | **21.4%** | **18.5%** | **166.3%** | **-27.4%** |
| Historical 9 (2021 top-10) | 1.078 | 17.3% | 16.1% | 121.9% | -18.9% |
| Expanded 15 (current + fallen) | 1.263 | 21.2% | 16.7% | 167.1% | -23.9% |
| VOO Benchmark | 0.741 | 12.5% | 16.8% | 73.2% | -24.5% |

### Survivorship Bias Estimate (US)

| Metric | Bias (Current vs Historical) |
|-|-|
| Sharpe ratio inflation | +0.077 |
| Annual return inflation | +4.1% per year |
| 5-year total return inflation | +44.3 percentage points |
| Volatility difference | +2.4% (current is MORE volatile) |

**The annual return bias of +4.1% per year is severe.** This exceeds the Elton, Gruber, Blake (1996) estimate of ~1-2% per year for mutual funds, which is expected because we are selecting individual stocks (higher dispersion) rather than funds.

**Counterintuitive finding:** The expanded 15-stock universe (Sharpe 1.263) actually has a HIGHER Sharpe than the current 9-stock universe (Sharpe 1.154). This suggests our concentrated universe is suboptimal from a diversification standpoint, adding the "fallen angels" improves risk-adjusted returns because they are less correlated with mega-cap tech.

## Results: India

### Individual 5-Year Annualized Returns (NSE)

| Ticker | 5Y Ann Return | Status |
|-|-|-|
| NTPC.NS | +32.8% | Current |
| BHARTIARTL.NS | +28.7% | Current |
| SBIN.NS | +25.6% | Current |
| SUNPHARMA.NS | +24.5% | Current |
| LT.NS | +22.1% | Current |
| TITAN.NS | +21.9% | Current |
| ICICIBANK.NS | +17.1% | Current |
| MARUTI.NS | +14.1% | Current |
| ITC.NS | +11.8% | Current |
| AXISBANK.NS | +11.9% | Current |
| BAJFINANCE.NS | +11.0% | Current |
| ADANIENT.NS | +10.2% | Current |
| HCLTECH.NS | +9.9% | Current |
| RELIANCE.NS | +8.7% | Current |
| HDFCBANK.NS | +1.6% | Current |
| INFY.NS | +0.6% | Current |
| KOTAKBANK.NS | +0.3% | Current |
| WIPRO.NS | -0.6% | Current |
| TCS.NS | -3.3% | Current |
| HINDUNILVR.NS | -1.1% | Current |
| **VEDL.NS** | **+43.7%** | **Fallen (outperformed!)** |
| **YESBANK.NS** | **+2.9%** | **Fallen (survived but barely)** |
| **INDUSINDBK.NS** | **-2.8%** | **Fallen** |
| **ZEEL.NS** | **-16.9%** | **Fallen (destroyed value)** |

**Note:** DHFL (Dewan Housing) was delisted after fraud/insolvency, complete loss. TATAMOTORS was reorganized. These stocks could not be downloaded, which is itself evidence of survivorship bias: the worst outcomes are invisible in our data.

### India Portfolio Comparison

| Portfolio | Sharpe | Ann Return | 5Y Total | Max DD |
|-|-|-|-|-|
| Current 20 | 1.056 | 14.6% | 95.3% | -15.2% |
| Historical 20 (with fallen angels) | 0.898 | 13.1% | 80.3% | -17.1% |
| Nifty 50 | ~0.6 | 9.2% | n/a | n/a |

**India survivorship bias: +1.5% per year.** Lower than the US bias because the India universe is more diversified (20 stocks vs 9) and the fallen angels (YESBANK, VEDL, ZEEL, INDUSINDBK) are a smaller fraction of the total.

## Literature Review

### Elton, Gruber, Blake (1996), "Survivorship Bias and Mutual Fund Performance"
- Found survivorship bias inflates average fund returns by **0.9% per year** for equity funds
- For growth-oriented funds: bias of **1.5-2.0% per year**
- Our finding of +4.1% for individual mega-cap stocks is consistent: individual stock selection has higher dispersion than fund selection

### Brown, Goetzmann, Ibbotson, Ross (1992), "Survivorship Bias in Performance Studies"
- Survivorship bias can create the appearance of predictability where none exists
- A portfolio of "survivors" will always look good in hindsight
- **Key quote:** "If the data set includes only those funds that have survived [...] the average performance is upward biased"

### Rohleder, Scholz, Wilkens (2011), "Survivorship Bias and Mutual Fund Performance: Relevance, Significance, and Methodical Differences"
- Bias is **larger for small-cap and concentrated portfolios** (relevant: our 9-stock US universe is extremely concentrated)
- Bias increases with the length of the backtest period

### Relevance to Our Engine
- Every backtest we run (walk-forward included) uses tickers selected with knowledge of which stocks became mega-caps
- The walk-forward methodology mitigates *signal overfitting* but does NOT mitigate *universe selection bias*
- Our reported Sharpe ratios, alpha, and returns are ALL inflated by this bias

## Transaction Cost Analysis

Survivorship bias is orthogonal to transaction costs. However, the bias compounds with transaction cost assumptions: if we overstate gross returns by 4.1%/year and understate costs by even 50bps/year, the combined error is 4.6%/year, enough to turn a negative-alpha strategy into an apparently positive one.

## Regime Analysis

Survivorship bias is **not regime-dependent**, it inflates returns in both bull and bear markets, because the universe selection occurred before any regime detection. However, the bias is likely LARGER during recovery periods (2022-2023 bear market recovery) because the stocks that recovered fastest are disproportionately in our current universe (NVDA recovered from -65% to +1160% cumulative).

## Quantification Summary

| Metric | US Bias | India Bias |
|-|-|-|
| Annual return inflation | +4.1%/yr | +1.5%/yr |
| Sharpe ratio inflation | +0.077 | +0.158 |
| 5-year total return inflation | +44.3 pp | +15.0 pp |
| Invisible delistings | 0 | 2 (DHFL, TATAMOTORS) |

**Total estimated bias on our backtest alpha:**
- US engine claims ~X% alpha. Of that, approximately 4.1% per year is attributable to survivorship bias in universe selection.
- India engine claims ~Y% alpha. Of that, approximately 1.5% per year is survivorship bias, plus an unknown amount from the 2 delisted stocks we cannot measure.

## Mitigation Recommendations

1. **Immediate:** Add prominent disclaimer to all performance metrics: "Returns are computed on a survivorship-biased universe and are likely overstated by 2-4% annually."
2. **Medium-term:** Use point-in-time S&P 500 constituents from CRSP or Sharadar for backtesting.
3. **Quick win:** Add the fallen angels (GE, XOM, WFC, IBM, T, INTC) to the tradeable universe. The expanded 15-stock portfolio has BETTER risk-adjusted returns (Sharpe 1.263 vs 1.154) due to diversification benefits.
4. **Intellectual honesty:** When reporting walk-forward alpha, subtract the survivorship bias estimate. If WF alpha is 3% and survivorship bias is 4.1%, the true alpha is likely negative.

## Conclusion and Recommendation

**CRITICAL FINDING, INVESTIGATE FURTHER**

The survivorship bias in our universe is substantial: +4.1% per year for the US engine, +1.5% per year for the India engine. This is the single largest source of inflated performance in the entire system. Any reported alpha below 4.1% (US) or 1.5% (India) should be assumed to be zero or negative after bias correction.

Until a survivorship-bias-free backtest is implemented, all performance claims should carry an explicit disclaimer.

**Actionable immediately:** Expanding the US universe from 9 to 15 stocks (adding the fallen angels) would paradoxically IMPROVE the portfolio while reducing survivorship bias. This is a rare case where the honest thing to do is also the profitable thing to do.
