# Sector-Equal-Weight Deep Validation

**Date:** 2026-04-02
**Script:** `data/research/sector_ew_deep_validation.py`
**Raw results:** `data/research/deep_validation_results.json`

## 1. Executive Summary

Sector-equal-weight (SEW) shows a **consistent but statistically insignificant** improvement over naive equal weight (EW) for India stocks. The walk-forward Sharpe improvement is +0.066 (1.06 vs 1.00), with a bootstrap 95% CI of [-0.12, +0.22] that includes zero. The improvement persists across ALL time sub-periods, ALL universe sizes (96-100% of random samples show positive improvement), ALL rebalance frequencies, and ALL transaction cost levels up to 50bps. It survives COVID exclusion and sector perturbation. However, the rolling 2-year analysis reveals the improvement is positive in only 59% of windows, barely better than a coin flip. In the US market, SEW actually HURTS Sharpe by -0.10, suggesting the India result depends on specific sector-stock count imbalances (banks 5 stocks, telecom/pharma/energy 1 stock each). **Verdict: ROBUST direction, FRAGILE magnitude.** The effect is real but small, driven by the specific Indian market structure where single-stock sectors (Bharti Airtel, Sun Pharma, Reliance) have outperformed the overrepresented banking sector. This is a portfolio construction default, not a source of excess return.

## 2. Walk-Forward Results

Rolling 12-month train window, 1-month out-of-sample, 75 OOS months total.

| Metric | Sector EW | Naive EW | Difference |
|-|:-:|:-:|:-:|
| OOS Sharpe | 1.0619 | 0.9962 | **+0.0657** |
| Ann. Alpha vs Naive | +2.09% | n/a | n/a |
| Max Drawdown | -22.28% | -22.64% | +0.36% |

**Bootstrap 95% CI on Sharpe Difference:** [-0.1214, +0.2177], median +0.0592

The CI includes zero. With 75 months of OOS data, we cannot reject the null hypothesis that SEW and naive-EW have identical risk-adjusted returns. The median improvement (+0.06) is positive but modest. The walk-forward Sharpe (1.06) is noticeably lower than the full-sample Sharpe (1.23), which is expected, full-sample results always look better.

**Assessment:** Directionally positive but not statistically significant. The full-sample Sharpe of 1.22 overstates the achievable OOS performance.

## 3. Parameter Sensitivity

### 3.1 Number of Sector Buckets (Random Assignment)

| Buckets | SEW Sharpe | Naive Sharpe | Improvement |
|:-:|:-:|:-:|:-:|
| 5 | 1.0802 | 1.0802 | 0.0000 |
| 6 | 1.0990 | 1.0802 | +0.0188 |
| 7 | 1.0601 | 1.0802 | -0.0201 |
| 8 | 1.0720 | 1.0802 | -0.0082 |
| 9 | 1.0928 | 1.0802 | +0.0126 |
| 10 | 1.0802 | 1.0802 | 0.0000 |
| **Original (8 sectors, real mapping)** | **1.2289** | **1.0802** | **+0.1487** |

**Critical finding:** Random sector assignments produce improvements of -0.02 to +0.02, essentially noise around zero. The original sector mapping produces +0.15. This means **the improvement is NOT from the sector-equal-weight mechanism itself, but from the SPECIFIC sector assignments** in INDIA_SECTOR_MAP. The real driver is upweighting Bharti Airtel, Sun Pharma, Bajfinance, and Reliance (from 5% each to 12.5% each) while downweighting banks (from 25% to 12.5%).

### 3.2 Universe Size Sensitivity

| Size | Mean Improvement | Median | % Positive | Min | Max |
|:-:|:-:|:-:|:-:|:-:|:-:|
| 12 stocks | +0.1089 | +0.0974 | 98.0% | -0.048 | +0.232 |
| 15 stocks | +0.1229 | +0.1171 | 98.0% | -0.009 | +0.240 |
| 18 stocks | +0.1469 | +0.1548 | 100.0% | +0.058 | +0.241 |
| 20 stocks | +0.1487 | +0.1487 | 100.0% | +0.149 | +0.149 |

Strong result: 96-100% of random subsets show positive improvement. The effect persists across universe sizes, though it strengthens with more stocks (more sector imbalance to correct).

### 3.3 Rebalance Frequency

| Frequency | SEW Sharpe (0bps) | Naive Sharpe (0bps) | Improvement | SEW Turnover | Naive Turnover |
|-|:-:|:-:|:-:|:-:|:-:|
| Weekly | 1.2174 | 1.0772 | +0.1402 | 2.37% | 2.35% |
| Biweekly | 1.2155 | 1.0747 | +0.1408 | 3.33% | 3.31% |
| Monthly | 1.2289 | 1.0802 | +0.1487 | 5.02% | 4.95% |
| Quarterly | 1.2291 | 1.0793 | +0.1498 | 8.77% | 8.51% |

The improvement is stable across all frequencies (~0.14-0.15). Turnover difference between SEW and naive is negligible (0.02-0.26% per period). Monthly or quarterly rebalance is optimal, quarterly has slightly better Sharpe improvement and lower cumulative costs from fewer rebalances.

**At 15bps cost:** Weekly=+0.1401, Biweekly=+0.1406, Monthly=+0.1486, Quarterly=+0.1497. Costs barely dent the improvement because both strategies have nearly identical turnover.

### 3.4 Sector Perturbation (20% Random Reassignment)

| Metric | Value |
|-|:-:|
| Mean Improvement | +0.0846 |
| Median Improvement | +0.0859 |
| Std Dev | 0.0585 |
| % Positive | 92.0% |
| Range | [-0.063, +0.253] |

Perturbing 20% of sector assignments still produces positive improvement 92% of the time, but the mean drops from +0.15 to +0.08. This confirms the specific sector mapping matters, the improvement is partially robust to misassignment but degrades meaningfully.

## 4. Time-Period Robustness

### 4.1 Sub-Period Analysis

| Period | SEW Sharpe | Naive Sharpe | Diff | Bootstrap CI | Zero in CI? |
|-|:-:|:-:|:-:|:-:|:-:|
| Pre-COVID (2019-2020)* | 2.2658 | 1.8676 | +0.398 | [-0.86, +2.05] | YES |
| Post-COVID (2020-2025) | 1.3131 | 1.2075 | +0.106 | [-0.11, +0.22] | YES |
| COVID window (2018-2022) | 1.4455 | 1.3190 | +0.127 | [-0.21, +0.25] | YES |
| Excl. COVID crash | 1.5755 | 1.4952 | +0.080 | [-0.11, +0.25] | YES |

*Pre-COVID period only has 210 trading days (~10 months), so the very high Sharpe numbers and wide CI are expected.

SEW outperforms in EVERY sub-period. The improvement is largest pre-COVID (+0.40) and smallest when excluding the COVID crash (+0.08). This suggests some of the improvement comes from crash behavior, SEW's more diversified sector allocation provides modest protection during drawdowns.

**Bootstrap CIs include zero in ALL periods.** Not a single sub-period achieves statistical significance.

### 4.2 Rolling 2-Year Windows

| Metric | Value |
|-|:-:|
| Number of windows | 64 |
| Mean improvement | +0.0411 |
| Median improvement | +0.0222 |
| % Positive | **59.4%** |
| Range | [-0.232, +0.266] |
| Std Dev | 0.122 |

**This is the most honest test.** Only 59.4% of 2-year windows show SEW outperforming. The median improvement is a tiny +0.02 Sharpe. The range is wide: some windows show SEW underperforming by -0.23 Sharpe. The full-sample result of +0.15 is driven by a subset of favorable windows where the single-stock sectors (telecom, pharma, energy) happened to outperform banking.

## 5. Transaction Cost Analysis

| Round-Trip Cost | SEW Sharpe | Naive Sharpe | Improvement |
|:-:|:-:|:-:|:-:|
| 0 bps | 1.2289 | 1.0802 | +0.1487 |
| 5 bps | 1.2269 | 1.0782 | +0.1487 |
| 10 bps | 1.2248 | 1.0762 | +0.1486 |
| 15 bps | 1.2228 | 1.0742 | +0.1486 |
| 20 bps | 1.2207 | 1.0722 | +0.1485 |
| 30 bps | 1.2167 | 1.0683 | +0.1484 |
| 50 bps | 1.2085 | 1.0603 | +0.1482 |

**Breakeven cost: >50bps** (improvement never disappears)

The improvement is virtually cost-immune because both strategies have nearly identical monthly turnover (~5%). The excess turnover of SEW over naive-EW is only 0.07% per month (0.85% annually). With 3% excess annual return and 0.85% excess turnover, the breakeven cost is absurdly high (35,000+ bps), meaning transaction costs are irrelevant to the SEW vs naive-EW comparison.

**India Realistic Round-Trip Cost:** ~9.9 bps (STT 2.5bps + brokerage 6bps + GST 1.1bps + stamp 0.3bps). Well below breakeven.

## 6. Alternative Strategy Comparison

All at 15bps cost, monthly rebalance, full period.

| Strategy | Sharpe | Ann. Return | Ann. Vol | Max DD | Monthly CVaR | Turnover |
|-|:-:|:-:|:-:|:-:|:-:|:-:|
| **Sector EW** | **1.2228** | **21.85%** | 17.87% | -36.20% | -11.41% | 5.02% |
| Naive EW | 1.0742 | 18.85% | 17.55% | -36.73% | -11.56% | 4.95% |
| Market Cap | 1.0263 | 18.26% | 17.79% | -36.69% | -11.38% | 4.62% |
| Inv. Volatility | 1.0647 | 18.09% | 16.99% | -36.68% | -11.53% | 10.34% |
| Min. Variance | 0.8920 | 14.36% | 16.09% | -34.01% | -13.58% | 97.87% |

Sector EW dominates on Sharpe. It has the highest return (+3% over naive) with similar volatility. Inverse-volatility provides slightly lower vol but at 2x the turnover. Min-variance has the lowest drawdown (-34% vs -36%) but much worse Sharpe and catastrophic turnover (98% monthly).

**Key insight:** All strategies have similar max drawdowns (~34-37%). The differentiation is entirely in returns. SEW's 3% excess return comes from overweighting the historically strong single-stock sectors.

## 7. Turnover Analysis

| Metric | Sector EW | Naive EW |
|-|:-:|:-:|
| Avg. Monthly Turnover | 5.02% | 4.95% |
| Excess Annual Turnover | 0.85% | n/a |
| Excess Annual Return | +3.0% | n/a |
| Breakeven Cost | 35,430 bps | n/a |
| Trades per Rebalance | 20 | 20 |

Both strategies trade the same 20 stocks at each rebalance. Turnover is nearly identical because both reset to fixed weights. The tiny turnover difference comes from slightly different drift patterns (SEW has more concentrated positions in single-stock sectors, which drift more).

**Execution is trivial.** 20 trades per month, ~5% turnover, at ~10bps realistic cost = 0.5% annual drag. Identical for both strategies.

## 8. Survivorship Bias Assessment

### Stocks Dropped from Nifty 50 Since 2019
YESBANK.NS, ZEEL.NS, VEDL.NS, GAIL.NS, INFRATEL.NS (delisted), IBULHSGFIN.NS (delisted), UPL.NS

### Replacement Tests (20 trials, replacing 2-3 stocks with ex-Nifty/mid-cap alternatives)

| Metric | Value |
|-|:-:|
| Trials | 20 |
| Mean SEW improvement | +0.2038 |
| Median SEW improvement | +0.2118 |
| % Positive | **100.0%** |
| Range | [+0.010, +0.338] |

**The SEW improvement actually INCREASES when including dropped stocks.** This is because dropped stocks (Yes Bank -99%, ZEEL, etc.) are typically poor performers that would hurt whichever sector they belong to. SEW limits damage from any single sector, while naive-EW spreads the damage more evenly across the portfolio. The improvement went from +0.15 (original) to +0.20 (with survivorship-biased replacements).

**Hypothesis test:** Survivorship bias, if anything, UNDERSTATES the SEW advantage. Including poor performers (which is what true no-survivorship-bias would do) makes sector diversification more valuable, not less. The DIFFERENCE between SEW and naive-EW is not inflated by survivorship.

Note: The script's automatic hypothesis label says "MAY AFFECT" because the improvement changed magnitude (from 0.15 to 0.20), but the direction is that survivorship bias makes the result CONSERVATIVE, not inflated.

## 9. US Out-of-Sample

| Metric | SEW | Naive EW | Difference |
|-|:-:|:-:|:-:|
| Sharpe | 1.1725 | 1.2765 | **-0.1040** |
| Ann. Return | 19.78% | 26.32% | -6.54% |
| Ann. Vol | 16.87% | 20.62% | -3.75% |
| Max DD | -26.63% | -27.29% | +0.66% |

**Bootstrap 95% CI:** [-0.3621, +0.2299], median -0.0953

**SEW hurts performance in the US.** By reducing tech weight from 44% to 20%, SEW misses the massive tech rally (NVDA, AAPL, MSFT). The lower vol (-3.75%) doesn't compensate for the 6.5% return sacrifice.

### Why It Fails in the US

1. **9 stocks is too few.** With only 5 sectors and 9 stocks, SEW gives 60% weight to three single-stock sectors (JNJ, KO, BRK-B) that underperform tech.
2. **Tech was the right bet.** Over 2019-2026, US tech dominance made the "concentration" in tech actually beneficial.
3. **India's structure is different.** India has 8 sectors with real diversification benefit. The single-stock sectors (Bharti, Sun Pharma, Reliance) outperformed the overweight banking sector. In the US, the single-stock sectors (JNJ, KO, BRK-B) underperformed the overweight tech sector.

**Implication:** SEW is not a universal diversification alpha. It works when the underweight sectors outperform the overweight sectors. In India 2019-2026, this happened. In the US 2019-2026, the opposite happened.

## 10. Final Verdict: ROBUST (with caveats)

### What IS Robust
- Direction of improvement: positive in ALL India time sub-periods
- Across universe sizes: 96-100% of random subsets show improvement
- Across rebalance frequencies: stable at ~0.14-0.15 improvement
- Transaction cost immunity: identical turnover, costs irrelevant
- Survivorship bias: if anything, understates the advantage
- Against alternatives: dominates naive-EW, MCW, inv-vol, min-var on Sharpe

### What IS Fragile
- **Statistical significance: NONE.** Bootstrap CI includes zero in every test
- **Rolling windows: only 59% positive.** Barely better than chance
- **Sector-specific:** Random sector assignments produce zero improvement. The SPECIFIC mapping of India sectors drives the result
- **US out-of-sample: FAILS.** SEW hurts Sharpe by -0.10 in the US
- **Magnitude uncertainty:** Walk-forward OOS Sharpe improvement is +0.07, not the +0.15 from full-sample. The full-sample Sharpe improvement is 2x the realistic OOS estimate
- **Regime dependent:** Works because India's single-stock sectors (telecom, pharma, energy) outperformed multi-stock sectors (banks). If banking rallies and telecom/pharma stall, SEW underperforms

### Honest Assessment

The sector-equal-weight improvement in India is **real but modest**. The true OOS Sharpe improvement is approximately +0.05 to +0.10, not the +0.16 reported in the full-sample study. The mechanism is not "sector diversification alpha", it is a specific bet that Bharti Airtel, Sun Pharma, Bajfinance, and Reliance deserve more weight than 5% each, and that banks deserve less than 25%. That bet has been correct over the past 5 years, but it is a sector allocation call, not a structural edge.

## 11. Deployment Scorecard

| Criterion | Result | Bar |
|-|-|-|
| Walk-forward CI excludes zero | No ([-0.12, +0.22]) | Yes |
| Parameter-robust | No (only the real sector mapping works; random mappings give -0.02 to +0.02) | 70% of grid |
| Time-period stable | Marginal (59.4% of rolling 2-year windows) | 70% |
| Tradeable after costs | Yes (breakeven above 50 bps) | above 15 bps |
| Survives survivorship test | Yes (improvement rises to +0.20) | no degradation |
| Out-of-sample market (US) | No (-0.10 Sharpe) | positive |
| Survives Bonferroni | No (approximate p about 0.25 against 0.00625) | p < 0.05/N |

Two of seven criteria pass. Sector equal weight is a defensible zero-cost default weighting with a concentration-limit rationale. It is not a validated source of excess return, and the full-sample +0.15 Sharpe figure should not be quoted; the walk-forward figure is +0.066 with a confidence interval that includes zero. The engine does not use sector equal weight; it applies a sector cap (40% US, 30% India) on top of HRP-blended weights.
