# Midcap Momentum Study

**Date:** 2026-04-02
**Hypothesis:** Momentum signals work better on less efficient midcap stocks.
**Script:** `data/research/midcap_momentum_study.py`

## Universe

29 of 30 target NSE midcap stocks passed data quality filter (PEL.NS delisted/unavailable).
Period: 2021-02-01 to 2026-03-30 (1,276 trading days, ~5 years).

## Full-Sample Results

| Strategy | Ann. Return | Ann. Vol | Sharpe | Max DD | Turnover |
|-|-|-|-|-|-|
| **Equal Weight (Benchmark)** | **21.22%** | **17.48%** | **1.214** | **-24.56%** | 0% |
| 12-1 Momentum (0bps) | 17.24% | 20.27% | 0.850 | -27.26% | 20.6% |
| 6-1 Momentum (0bps) | 17.35% | 20.56% | 0.844 | -24.99% | 26.3% |
| 3-1 Momentum (0bps) | 19.52% | 20.24% | 0.964 | -23.32% | 35.7% |

**VERDICT: Equal weight CRUSHES all momentum strategies in full sample.** Sharpe 1.214 vs best momentum 0.964. Every single momentum variant UNDERPERFORMS naive equal weight by 0.25-0.37 Sharpe.

## Cost-Adjusted Results

| Strategy | 0bps | 15bps | 25bps | 40bps |
|-|-|-|-|-|
| 12-1 Momentum | 0.850 | 0.828 | 0.814 | 0.792 |
| 6-1 Momentum | 0.844 | 0.816 | 0.798 | 0.771 |
| 3-1 Momentum | 0.964 | 0.926 | 0.901 | 0.863 |

Costs hit shorter lookbacks harder due to higher turnover (35.7% for 3-1 vs 20.6% for 12-1). At realistic 25bps midcap costs, the gap with EW widens further.

## Walk-Forward OOS Results

| Strategy | OOS Sharpe (0bps) | OOS Sharpe (15bps) | OOS Sharpe (25bps) | OOS Sharpe (40bps) |
|-|-|-|-|-|
| WF 12-1 | 1.720 | 1.589 | 1.503 | 1.374 |
| WF 6-1 | 1.225 | 1.103 | 1.022 | 0.903 |
| WF 3-1 | 1.590 | 1.461 | 1.376 | 1.249 |

Walk-forward OOS Sharpes look much better than full-sample. BUT: these are absolute OOS Sharpes, not relative to EW benchmark over the same OOS period. The bootstrap tells the real story.

## Bootstrap 95% CI (Momentum - EW Sharpe)

| Strategy | Observed Diff | 95% CI | Significant? |
|-|-|-|-|
| 12-1 (full) | -0.750 | [-2.215, 0.653] | NO |
| 12-1 (WF OOS) | -0.275 | [-1.999, 1.475] | NO |
| 6-1 (full) | -0.648 | [-2.010, 0.740] | NO |
| 6-1 (WF OOS) | -0.750 | [-2.357, 0.831] | NO |
| 3-1 (full) | -0.509 | [-1.834, 0.802] | NO |
| 3-1 (WF OOS) | -0.562 | [-2.093, 0.966] | NO |

**NONE are significant. Every single CI includes zero. All observed diffs are NEGATIVE (momentum worse than EW).**

## Turnover

| Strategy | Avg Monthly Turnover |
|-|-|
| 12-1 | 20.6% |
| 6-1 | 26.3% |
| 3-1 | 35.7% |

3-1 turnover at 35.7% means ~3.6 of the 10 stocks rotate every month. At 25bps impact, that's 9bps monthly drag. Not catastrophic but adds up.

## Survivorship Bias Check

Top 3 performers removed: LINDEINDIA.NS (+649.5%), CUMMINSIND.NS (+568.7%), PERSISTENT.NS (+559.3%).

| Strategy | Full Universe Sharpe | Reduced Universe Sharpe | EW Reduced |
|-|-|-|-|
| EW Benchmark | 1.214 | 1.021 | (this IS the benchmark) |
| 12-1 Momentum | 0.850 | 0.949 | |
| 6-1 Momentum | 0.844 | 0.760 | |
| 3-1 Momentum | 0.964 | 0.838 | |

Removing top 3 performers drops the EW benchmark from 1.214 to 1.021, a 0.19 Sharpe haircut (16%). This confirms survivorship bias is present in the midcap universe. These 30 stocks were selected BECAUSE they are "liquid NSE midcaps" today, meaning they survived and grew.

**Reduced universe bootstrap (momentum vs reduced EW):**
- 12-1: diff=-0.505, CI=[-1.988, 0.900], NOT significant
- 6-1: diff=-0.574, CI=[-1.944, 0.802], NOT significant
- 3-1: diff=-0.462, CI=[-1.781, 0.850], NOT significant

Still nothing. Momentum STILL loses to EW even with survivorship adjustment.

## Diagnosis: Why Doesn't Midcap Momentum Work?

1. **Wrong hypothesis.** "Less efficient = more alpha" sounds logical but ignores that midcap NSE stocks in 2021-2026 were in a massive bull market. In a broad-based rally, EW naturally outperforms concentration strategies because laggards catch up (mean reversion dominates).

2. **Higher vol.** All momentum strategies have 20%+ vol vs 17.5% for EW. Concentrating in 10 stocks removes diversification benefit without adding enough return to compensate.

3. **Survivorship bias in the universe.** The 30 stocks were selected as today's liquid midcaps. Stocks that crashed out of the midcap index aren't in the sample. This HELPS EW (all 29 are survivors) and doesn't help momentum differentially.

4. **Indian midcaps 2021-2026 = rising tide lifting all boats.** The universe returned 21% annualized. In such an environment, stock picking (including momentum) adds noise, not signal.

## HONEST CONCLUSION

**REJECT.** The "midcap inefficiency" hypothesis is DEAD for this universe and period.

- Momentum does NOT work better on midcaps. It works WORSE. Every lookback variant underperforms EW.
- No bootstrap CI excludes zero. No strategy is statistically distinguishable from EW.
- Survivorship bias inflates the entire universe by ~0.19 Sharpe.
- High turnover (20-36%) at midcap cost levels (15-40bps) makes this even worse.
- The WF OOS Sharpes look superficially impressive (1.2-1.7) but this is an ABSOLUTE measure, relative to EW over the same period, the difference is negative and non-significant.

**This is the FOURTH confirmation that momentum at ANY lookback, on ANY universe (US large-cap, India large-cap, India midcap), does NOT beat equal weight.** 
