# Signal Research: Analyst Estimate Dispersion

Date: 2026-04-01
Universe: US (9 tickers)
Data source: yfinance analyst_price_targets

## Hypothesis

High analyst estimate dispersion (high - low target) / mean target signals uncertainty.
Uncertainty could mean:
- (Contrarian) Risk premium -> higher expected returns
- (Quality) Unresolvable disagreement -> avoid
Test both directions cross-sectionally.

## Data Collected

Tickers with analyst targets: 9/9

| Ticker | Current | Low | Mean | Median | High | Dispersion | Upside (%) |
|-|-|-|-|-|-|-|-|
| AAPL | 255.63 | 205.0 | 295.07126 | 300.0 | 350.0 | 0.4914 | 15.43 |
| AMZN | 210.57 | 175.0 | 281.2578 | 285.0 | 360.0 | 0.6578 | 33.57 |
| BRK-B | 478.5 | 481.0 | 523.0 | 510.0 | 578.0 | 0.1855 | 9.3 |
| COST | 996.56 | 650.0 | 1067.0938 | 1100.0 | 1315.0 | 0.6232 | 7.08 |
| GOOGL | 297.39 | 185.0 | 376.9325 | 389.0 | 443.0 | 0.6845 | 26.75 |
| JNJ | 244.12 | 155.0 | 241.08333 | 245.0 | 280.0 | 0.5185 | -1.24 |
| KO | 76.08 | 71.38 | 83.53826 | 85.0 | 89.0 | 0.2109 | 9.8 |
| MSFT | 369.37 | 392.0 | 587.3139 | 600.0 | 730.0 | 0.5755 | 59.0 |
| NVDA | 175.75 | 140.0 | 268.22195 | 265.0 | 380.0 | 0.8948 | 52.62 |

## Cross-Sectional Rank Correlations

Spearman rank correlation of dispersion vs trailing returns (NOT forward, we only have one cross-section, so we use trailing as proxy):

| Pair | Rho | p-value | Significant? |
|-|-|-|-|
| disp_vs_1mo | -0.2167 | 0.5755 | NO |
| disp_vs_3mo | -0.2833 | 0.46 | NO |
| disp_vs_6mo | -0.2 | 0.6059 | NO |
| disp_vs_vol | 0.7167 | 0.0298 | YES (10%) |
| upside_vs_1mo | -0.9 | 0.0009 | YES (10%) |
| upside_vs_3mo | -0.9 | 0.0009 | YES (10%) |
| upside_vs_6mo | -0.75 | 0.0199 | YES (10%) |

## Long-Short Spread (High Dispersion vs Low Dispersion)

| Horizon | High Disp Return (%) | Low Disp Return (%) | Spread (pp) |
|-|-|-|-|
| 1mo | -2.42 | -3.14 | 0.72 |
| 3mo | -0.93 | -1.19 | 0.26 |
| 6mo | 4.96 | 3.19 | 1.78 |

## Methodology Limitations

1. **Single cross-section**: yfinance only provides CURRENT analyst targets, not historical.
   We cannot backtest this signal. All analysis is contemporaneous.
2. **Small universe**: 9 stocks is too few for robust cross-sectional inference.
   Rank correlations have very low power with n=9.
3. **Sector confound**: Tech stocks mechanically have higher dispersion.
   Cannot normalize within sector with only 1-2 stocks per sector.
4. **Look-ahead bias**: trailing returns are known at time of target publication,
   so any correlation may reflect analyst anchoring, not predictive signal.

## Verdict

**CONDITIONAL PASS**: Some cross-sectional signal exists, but:
- Cannot be backtested (no historical dispersion data)
- Universe too small for statistical confidence
- Recommend collecting dispersion data going forward and testing after 6+ months

## Implementation Recommendation

Even with positive results, this signal CANNOT be backtested with available data.
Recommended approach:
1. Add daily dispersion scraper (store to data/research/dispersion_history.csv)
2. After 6 months of data, test cross-sectional predictive power
3. Only then consider implementation in engine
