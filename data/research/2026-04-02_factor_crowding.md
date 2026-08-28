# Factor Crowding Analysis: Momentum Signal

**Date:** 2026-04-02
**Signal:** 12-1 Momentum (and variants)
**Status:** ANALYSIS

## Signal Description and Hypothesis

**Hypothesis:** Our primary alpha signal, 12-month momentum, skip most recent month (12-1), is the most widely known and deployed momentum signal in quantitative finance. If our signal output is highly correlated with momentum ETFs (MTUM, QMOM, SPMO), we are effectively running a momentum ETF with extra operational complexity and no differentiated edge.

**The crowding concern:** When too much capital chases the same signal, (a) the signal's forward returns compress, (b) crowded exits cause catastrophic crashes (momentum crashes), and (c) transaction costs increase as everyone tries to trade the same names on the same schedule.

## Data Used and Time Period

- **Period:** April 2021, April 2026 (5 years)
- **Source:** Yahoo Finance via yfinance
- **Our universe:** AAPL, GOOGL, AMZN, NVDA, JNJ, KO, BRK-B, COST, MSFT
- **Momentum ETFs:** MTUM (iShares MSCI USA Momentum Factor), QMOM (Alpha Architect Quantitative Momentum), SPMO (Invesco S&P 500 Momentum)
- **Benchmark:** VOO (Vanguard S&P 500)

## Methodology

1. Construct a long/short momentum portfolio from our 9-stock universe: rank by 12-1 momentum, go long top half, short bottom half, rebalance daily
2. Compare this signal's returns to MTUM ETF returns
3. Compute full-period and rolling 63-day correlation
4. Test alternative momentum definitions (6-1, 3-1, 12-0, 12-1 vol-adjusted)
5. Analyze crash characteristics: skewness, kurtosis, worst months

## Results: Momentum Signal Performance

### Our 12-1 Momentum L/S Portfolio

| Metric | Value |
|-|-|
| Annualized return | +3.5% |
| Annualized volatility | 21.3% |
| Sharpe ratio | 0.164 |
| Skewness | -0.060 |
| Kurtosis | 2.315 |
| 5th percentile daily return | -2.15% |
| 1st percentile daily return | -3.42% |

**The Sharpe ratio of 0.164 is essentially zero.** A t-statistic of 0.164 * sqrt(981/252) = 0.32 is not statistically significant. The standalone 12-1 momentum L/S signal in our 9-stock universe has no detectable alpha over this period.

### Worst Months (Momentum Crashes in Our Universe)

| Month | L/S Return |
|-|-|
| 2023-01 | -15.19% |
| 2025-02 | -12.87% |
| 2022-07 | -9.64% |
| 2024-07 | -7.65% |
| 2025-06 | -7.62% |
| 2022-05 | -6.88% |
| 2025-03 | -6.81% |
| 2022-11 | -6.59% |
| 2025-08 | -5.94% |
| 2024-08 | -5.59% |

**A -15.19% month (January 2023) and -12.87% month (February 2025) in a 9-stock L/S portfolio is severe.** These are the small-scale versions of the momentum crashes documented by Daniel and Moskowitz (2016).

## Results: Correlation with Momentum ETFs

### L/S Signal vs MTUM

| Metric | Value |
|-|-|
| Full-period correlation | 0.355 |
| Rolling 63d correlation (mean) | 0.359 |
| Rolling 63d correlation (min) | -0.469 |
| Rolling 63d correlation (max) | 0.842 |
| Rolling 63d correlation (std) | 0.372 |

**The L/S signal correlation with MTUM is moderate at 0.355.** This is lower than the 0.8 threshold that would indicate we are a pure momentum ETF clone. The low correlation is partly because our universe is only 9 stocks (MTUM holds ~125 stocks), and our L/S construction differs from MTUM's long-only tilt.

### Equal-Weight Portfolio vs Momentum ETFs

| Comparison | Correlation |
|-|-|
| Our EW portfolio vs MTUM | 0.766 |
| Our EW portfolio vs SPMO | 0.786 |
| Our EW portfolio vs QMOM | 0.609 |

**This is the real concern.** Our equal-weight portfolio of 9 mega-caps has a 0.766 correlation with MTUM and 0.786 with SPMO. This is not because of our momentum signal, it is because our universe IS the momentum universe. The same mega-cap tech stocks that dominate our portfolio dominate momentum ETFs.

**Implication:** Even before applying any signal, our universe selection implicitly loads on the momentum factor. The signal tilt adds incremental momentum exposure on top of an already momentum-heavy base.

## Results: Momentum Variant Comparison

| Variant | Sharpe | Ann Return | Ann Vol | Skewness |
|-|-|-|-|-|
| **12-1 (our signal)** | **0.164** | **+3.5%** | **21.3%** | **-0.060** |
| 6-1 | -0.117 | -2.4% | 20.9% | -0.067 |
| **3-1** | **0.864** | **+18.3%** | **21.1%** | **-0.228** |
| 12-0 (no skip) | -0.138 | -2.9% | 21.1% | -0.135 |
| 12-1 vol-adjusted | -0.060 | -1.2% | 19.7% | -0.028 |

**Key findings:**

1. **12-1 is not the best variant.** The 3-month momentum with 1-month skip (3-1) has a Sharpe of 0.864, vastly outperforming our 12-1 signal (0.164). This is a 5x improvement in Sharpe ratio.

2. **The 1-month skip matters enormously.** Without it (12-0), the signal reverses to negative returns (-2.9% annualized). This confirms the short-term reversal effect: stocks that performed well in the most recent month tend to mean-revert.

3. **6-1 momentum is negative.** The intermediate-term momentum signal does not work in our universe over this period.

4. **Vol-adjusted momentum is slightly negative.** Our vol_adj_momentum signal, which divides momentum by volatility, does not improve results in L/S testing.

5. **3-1 has the worst skewness (-0.228).** The variant with the best Sharpe also has the most negative skew, consistent with momentum crash theory: shorter-term momentum is more profitable but more crash-prone.

## Factor Crowding: Scale and Implications

### Estimated AUM in Momentum Strategies

| Category | Estimated AUM |
|-|-|
| MTUM (iShares) | ~$10B |
| SPMO (Invesco) | ~$3B |
| QMOM (Alpha Architect) | ~$500M |
| Other US momentum ETFs | ~$5B |
| Institutional momentum mandates | ~$200B+ (estimated) |
| **Total dedicated momentum capital** | **$200-300B** |

When this capital reverses simultaneously, the result is a momentum crash. The most extreme example: March 2009, when momentum stocks lost ~40% in a single month as value stocks rallied (Daniel and Moskowitz, 2016).

### Literature: Daniel and Moskowitz (2016), "Momentum Crashes"

Key findings relevant to us:
- Momentum has **positive unconditional expected returns** but **extreme negative conditional returns** during market recoveries
- Momentum crashes occur when the market rebounds after a crash: past losers (which momentum is short) rally violently
- The worst momentum crash in their sample: **-91.59% in a single month** (July 1932)
- Modern era worst: **~-40% in March 2009**
- Crash risk is concentrated in the first few months of market recovery after a bear market
- **Implication for us:** Our engine detects "crisis" regime and shifts to mean reversion. This is exactly the right thing to do, it reduces momentum exposure during the periods when momentum crashes are most likely.

### Barroso and Santa-Clara (2015), "Momentum Has Its Moments"

- Momentum volatility is predictable using past volatility
- Scaling momentum exposure inversely with predicted volatility eliminates crash risk
- **Implication:** Our vol_adj_momentum signal attempts this but does not work in L/S testing. This may be because our universe is too small (9 stocks) for the diversification needed to make volatility scaling effective.

## Crowding Detection: How Would We Know?

Potential crowding indicators (not implemented):

1. **Short interest concentration:** When momentum winners have unusually low short interest and momentum losers have unusually high short interest, the trade is crowded.
2. **ETF flow momentum:** If MTUM is seeing record inflows while momentum is performing well, the trade is getting crowded.
3. **Cross-sectional return dispersion:** When all stocks in our universe move together (high correlation), factor trades become fragile. We already monitor this (correlation_monitor).
4. **Signal correlation with consensus:** If our top picks match MTUM's top holdings, we have no informational edge.

## Transaction Cost Analysis

Our momentum signal rebalances monthly. With 5bps each way (10bps round-trip):
- Estimated annual turnover for 12-1 momentum: ~200% (based on typical institutional momentum strategies)
- Annual transaction cost drag: 200% * 10bps = 200bps = 2.0%
- With 3.5% gross return, net return = 1.5%, barely positive
- For the 3-1 variant (higher turnover ~400%): cost drag = 400bps = 4.0%, net return = 14.3%, still attractive

## Regime Analysis

The momentum signal's performance is regime-dependent:

- **Bull markets (risk_on):** Momentum works well because winners keep winning
- **Bear markets (risk_off):** Momentum continues to work (shorts outperform)
- **Recovery after crash (crisis-to-risk_on transition):** Momentum CRASHES because past losers rally violently

Our regime detection system correctly reduces momentum weight in crisis (from 0.35 to 0.10). However, the transition FROM crisis BACK to risk_on is the dangerous period, and our system does not explicitly handle this.

## Conclusion and Recommendation

**INVESTIGATE FURTHER**

### Findings Summary

1. **Our 12-1 momentum L/S signal has a Sharpe of 0.164, statistically indistinguishable from zero.** The signal has no standalone alpha in our 9-stock universe over the last 5 years.

2. **Our equal-weight portfolio correlates 0.77-0.79 with momentum ETFs** because our universe IS the momentum universe (mega-cap tech). We are implicitly loading on momentum factor through universe selection, not just through the signal.

3. **The L/S signal correlation with MTUM is 0.36**, moderate. We are not a pure MTUM clone, partly because our universe is much smaller.

4. **3-1 momentum (Sharpe 0.864) dramatically outperforms 12-1 (Sharpe 0.164)** in our universe. This is a potential quick win: switching the primary momentum lookback from 12 months to 3 months.

5. **Momentum crash risk is real.** Worst month: -15.19%. The regime-adaptive weight reduction in crisis mode is the correct mitigation, but the crisis-to-recovery transition remains unprotected.

### Recommendations

1. **Research priority:** Test 3-1 momentum as a replacement for 12-1 in the walk-forward framework. If it passes OOS validation, it would be a significant improvement.
2. **Crowding mitigation:** Add MTUM correlation as a regime indicator. When our portfolio correlation with MTUM exceeds 0.85 (rolling 63d), reduce momentum weight.
3. **Crash protection:** Implement the Barroso and Santa-Clara (2015) volatility-scaling approach, but across the composite signal rather than just momentum.
4. **Universe diversification:** The factor crowding problem is partly caused by having only 9 mega-cap stocks. Adding more stocks (including value and small-cap names) would reduce implicit momentum loading.
5. **Regime transition handling:** Add explicit handling for the crisis-to-risk_on transition. During the first 3 months after a crisis regime, keep momentum weight at crisis levels (0.10) rather than jumping to risk_on (0.35).

## Follow-up

The 3-1 versus 12-1 comparison above uses a five-year window. On a ten-year window the same long-short construction gives 3-1 Sharpe 0.158 and 12-1 Sharpe 0.225, and inside the full walk-forward portfolio the 24 lookback and skip variants span only 0.937 to 1.036 Sharpe. See momentum-lookback-study.md, section 12. The "5x improvement" is a window artifact and the recommendation to test 3-1 as a replacement is withdrawn.
