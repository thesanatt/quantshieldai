# Survivorship Bias Mitigation: Practical Approaches

**Date:** 2026-04-02
**Status:** IMPLEMENTATION RECOMMENDATIONS
**Builds on:** 2026-04-02_survivorship_bias.md

## Context

The survivorship study quantified survivorship bias in our backtest: selecting current winners (NVDA, AAPL, etc.)
and backtesting from 2021 creates an inherent look-ahead bias. This document proposes practical
mitigation strategies.

## The Problem We Cannot Fully Solve

True survivorship-bias-free backtesting requires point-in-time index constituent data:
"What were the S&P 500 top 10 by market cap on January 1, 2021?" This data exists
(S&P Capital IQ, Compustat) but is expensive and not available via yfinance.

We can, however, partially mitigate the bias using available data.

## Mitigation Strategy 1: Add "Fallen Angels"

**Approach:** Include stocks that were once top-10 large caps but subsequently underperformed.
This partially offsets the bias of only holding winners.

### US Fallen Angels (add to backtest universe)
- **GE** (General Electric), was #1 by market cap in 2000, massive decline through 2018
- **XOM** (ExxonMobil), top 5 until 2014, then energy bear market
- **WFC** (Wells Fargo), top 5 bank, then fake accounts scandal
- **IBM**, perennial large cap, 10-year underperformance
- **T** (AT&T), former largest telecom, chronic value trap
- **INTC** (Intel), former chip leader, lost to TSMC/NVDA

### India Fallen Angels
- **YESBANK.NS**, former Nifty 50 constituent, near-zero after fraud
- **VEDL.NS** (Vedanta), volatile commodity play, in and out of Nifty
- **ZEEL.NS** (Zee Entertainment), corporate governance issues
- **INDUSINDBK.NS**, former Nifty bank, underperformed peers

### Implementation

The engineer should:
1. Download fallen angel prices alongside current universe
2. In walk-forward backtest, at each rebalance point, select the top N stocks by trailing
   12-month market cap from the combined (current + fallen) universe
3. This simulates what a quant fund would have actually held at each point in time
4. Expected impact: Sharpe ratios decrease by 0.1-0.3 as fallen angels drag returns

### Limitation

This is still partially biased because we chose "fallen angels" with hindsight. A truly
unbiased approach requires historical S&P 500 constituent data. However, adding losers
is strictly more honest than only holding winners.

## Mitigation Strategy 2: Use ETF as Upper Bound

**Approach:** Compare our strategy return to VOO (which IS survivorship-bias-free by
construction, since it holds the actual S&P 500 constituents at each point in time).

Our walk-forward alpha is measured vs VOO. If alpha is positive after costs, the strategy
adds value relative to a bias-free benchmark, even if our absolute returns are inflated.

**This is already our methodology.** The key insight: alpha vs VOO is bias-free even if
absolute returns are biased. Our walk-forward alpha is measured against VOO, not against zero.

However, the stock-selection component of alpha is still biased: we are picking from
a pre-screened pool of winners. The true alpha from stock selection within S&P 500
constituents would be lower.

## Mitigation Strategy 3: Universe Rotation Robustness Test

**Approach:** Run the walk-forward backtest on 10 random subsets of S&P 500 stocks
(not just our 9 hand-picked winners). If the signal composite produces positive alpha
across most random universes, the alpha is not purely survivorship-driven.

### How to implement
1. Download top 50 S&P 500 stocks by current market cap
2. Randomly sample 9 stocks (without replacement), 10 times
3. Run walk-forward on each sample
4. Report distribution of Sharpe ratios and alphas

### Expected finding
If our signals work (not just our stock picks), most random samples should show positive
alpha. If only 1-2 of 10 samples show positive alpha, the edge is entirely in stock
selection (i.e., survivorship bias).

## Mitigation Strategy 4: Shorter Backtest Window

**Approach:** Limit backtest to 3 years instead of 5+. On a 3-year horizon, survivorship
bias is smaller because fewer stocks have time to dramatically diverge. The current top-10
are largely the same as the 2023 top-10.

**Tradeoff:** Fewer data points means wider confidence intervals and less statistical
power. A 3-year backtest with monthly rebalancing gives only 36 test periods.

## Quantification of Residual Bias

From the quantification study:
- Bias-free portfolio (including fallen angels) showed approximately 2-4% lower annual
  returns than our current universe
- Sharpe reduction: approximately 0.1-0.2
- Alpha vs VOO remains positive even with fallen angels included

**Bottom line:** Our alpha vs VOO is real but overstated by approximately 2-4% annually
due to universe selection bias. An honest Sharpe estimate should haircut our walk-forward
Sharpe by 0.1-0.2.

## Recommendation

| Priority | Action | Effort | Impact |
|-|-|-|-|
| 1 | Always report alpha vs VOO (bias-free benchmark) | Already done | High |
| 2 | Run universe rotation robustness test | Medium (1 script) | High |
| 3 | Add 3-4 fallen angels to backtest universe | Low (config change) | Medium |
| 4 | Shorter backtest window sensitivity | Low | Low |
| 5 | Get historical S&P 500 constituent data | High (paid data) | Highest |

**Verdict: INVESTIGATE FURTHER**

Survivorship bias inflates our absolute returns but our alpha measurement (vs VOO) is
largely robust. The universe rotation test (Strategy 3) would be the most informative
next step. If 8/10 random universes show positive alpha, we can be confident the signals
work beyond our specific stock picks.
