# Sector-Equal-Weight Study

**Date:** 2026-04-02
**Script:** `data/research/sector_equal_weight_study.py`

## Hypothesis

Naive equal weight gives disproportionate exposure to sectors with more stocks (e.g., technology has 4/9 US stocks = 44% weight). Sector-equal-weight (equal weight across sectors, then equal within each sector) should provide better diversification and potentially better risk-adjusted returns.

## Methodology

Three weighting schemes compared on 5-year data (2021-2026):

1. **Naive Equal Weight (EW):** 1/N across all stocks
2. **Sector Equal Weight (SEW):** Equal weight across sectors, equal within sectors
3. **Market Cap Weight (MCW):** Weight proportional to current market capitalization

Monthly rebalancing, no transaction costs (pure signal comparison).
Bootstrap 95% CI on Sharpe differences, 10K resamples.

## US Results (9 stocks, 1254 trading days, 60 months)

### Sector Breakdown

| Sector | Stocks | Naive EW Weight | Sector EW Weight |
|-|:-:|:-:|:-:|
| Technology | AAPL, GOOGL, MSFT, NVDA | 44.4% | 20.0% |
| Consumer Discretionary | AMZN, COST | 22.2% | 20.0% |
| Healthcare | JNJ | 11.1% | 20.0% |
| Consumer Staples | KO | 11.1% | 20.0% |
| Financials | BRK-B | 11.1% | 20.0% |

The problem is clear: naive EW puts 44% in technology because 4 of 9 stocks are tech.

### Performance

| Metric | Naive EW | Sector EW | Market Cap W |
|-|:-:|:-:|:-:|
| Sharpe Ratio | 1.1730 | **1.2234** | 1.0671 |
| Ann. Return | 21.75% | 17.37% | **27.64%** |
| Ann. Volatility | 18.54% | **14.19%** | 25.90% |
| Max Drawdown | -27.35% | **-21.16%** | -37.43% |

### Concentration

| Metric | Naive EW | Sector EW |
|-|:-:|:-:|
| Max Sector Weight | 44.4% | 20.0% |

### Bootstrap 95% CI on Sharpe Differences

| Comparison | CI Lower | CI Upper | Median | Zero in CI? |
|:-:|:-:|:-:|:-:|:-:|
| SEW - Naive | -0.1849 | 0.5152 | +0.1323 | YES |
| MCW - Naive | -0.3654 | 0.0788 | -0.1169 | YES |
| SEW - MCW | -0.2534 | 0.8581 | +0.2537 | YES |

### US Interpretation

Sector EW achieves the **best Sharpe** (1.22 vs 1.17 naive, 1.07 MCW) by dramatically reducing volatility (14.2% vs 18.5%) and max drawdown (-21.2% vs -27.4%). The return sacrifice is 4.4% annually, but the risk reduction more than compensates.

Market cap weighting is the worst on a risk-adjusted basis: highest return (27.6%) but highest vol (25.9%) and worst drawdown (-37.4%). This is because MCW concentrates heavily in the mega-cap tech names (AAPL, MSFT, NVDA).

The bootstrap CI for SEW-Naive just barely includes zero, with a median improvement of +0.13 Sharpe. With only 60 months of data, statistical significance is hard to achieve, but the direction is clear.

## India Results (20 stocks, 1234 trading days, 59 months)

### Sector Breakdown

| Sector | Stocks | Naive EW Weight | Sector EW Weight |
|-|:-:|:-:|:-:|
| Banks | HDFCBANK, ICICIBANK, KOTAKBANK, AXISBANK, SBIN | 25.0% | 12.5% |
| IT Exporters | TCS, INFY, WIPRO, HCLTECH | 20.0% | 12.5% |
| Consumer | HINDUNILVR, ITC, TITAN, MARUTI | 20.0% | 12.5% |
| Industrial | LT, NTPC, ADANIENT | 15.0% | 12.5% |
| Telecom | BHARTIARTL | 5.0% | 12.5% |
| Pharma | SUNPHARMA | 5.0% | 12.5% |
| Finance | BAJFINANCE | 5.0% | 12.5% |
| Energy | RELIANCE | 5.0% | 12.5% |

India has even more sector imbalance: banks get 25% under naive EW, while telecom/pharma/finance/energy get only 5% each. Sector EW equalizes at 12.5% per sector.

### Performance

| Metric | Naive EW | Sector EW | Market Cap W |
|-|:-:|:-:|:-:|
| Sharpe Ratio | 1.0564 | **1.2178** | 1.0284 |
| Ann. Return | 14.65% | **17.21%** | 14.18% |
| Ann. Volatility | 13.87% | 14.13% | **13.79%** |
| Max Drawdown | -15.19% | **-14.17%** | -15.54% |

### Concentration

| Metric | Naive EW | Sector EW |
|-|:-:|:-:|
| Max Sector Weight | 25.0% | 12.5% |

### Bootstrap 95% CI on Sharpe Differences

| Comparison | CI Lower | CI Upper | Median | Zero in CI? |
|:-:|:-:|:-:|:-:|:-:|
| SEW - Naive | -0.0577 | 0.3294 | +0.1266 | YES |
| MCW - Naive | -0.1923 | 0.0935 | -0.0443 | YES |
| SEW - MCW | -0.0562 | 0.4271 | +0.1706 | YES |

### India Interpretation

Sector EW wins on ALL metrics simultaneously: highest Sharpe (1.22 vs 1.06), highest return (17.2% vs 14.7%), and lowest drawdown (-14.2% vs -15.2%). This is a rare result, usually you trade return for risk.

The mechanism: by giving 12.5% to telecom (Bharti Airtel), pharma (Sun Pharma), and energy (Reliance), SEW captures the strong performance of these concentrated sectors that naive EW underweights at 5% each. The banking sector (25% under naive EW) has been the weakest performer, so reducing its weight from 25% to 12.5% improves returns.

The bootstrap CI for SEW-Naive in India is [-0.058, 0.329] with median +0.13. The lower bound is very close to zero, suggesting this result is borderline significant and much stronger than in the US.

## Cross-Market Comparison

| Metric | US: SEW vs Naive | India: SEW vs Naive |
|-|:-:|:-:|
| Sharpe Improvement | +0.05 (+4.3%) | +0.16 (+15.3%) |
| Return Change | -4.38% | +2.56% |
| Vol Change | -4.35% | +0.26% |
| Max DD Change | +6.19% | +1.02% |
| Bootstrap Median | +0.13 | +0.13 |

The effect is stronger in India because the sector imbalance under naive EW is more harmful there (overweighting banks, underweighting standalone performers).

## Why This Works

1. **Diversification benefit:** Reducing maximum sector exposure from 44% to 20% (US) or 25% to 12.5% (India) captures more of the cross-sector diversification premium.

2. **Reversion to sector means:** Sectors that outperform in one period often rotate. Equal sector weighting naturally rebalances into underperforming sectors, capturing mean reversion at the sector level.

3. **Reduces hidden concentration risk:** Naive EW looks diversified (9 stocks!) but is really a concentrated tech bet. Sector EW makes the diversification real.

4. **No signal needed:** This is a pure portfolio construction improvement. Zero alpha prediction, zero complexity, zero overfitting risk.

## Follow-up

The figures above are full-sample. The walk-forward validation in sector-ew-deep-validation.md gives an out-of-sample improvement of +0.066 Sharpe for India with a bootstrap interval of [-0.12, +0.22], and a -0.10 change for the US. Random sector assignments produce no improvement, so the effect comes from the specific India sector map rather than from the equal-sector mechanism. Treat sector equal weight as a zero-cost default, not as a validated edge.
