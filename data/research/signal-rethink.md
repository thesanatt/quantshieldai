# Signal Architecture Rethink: 4 Hypotheses Tested

**Date:** 2026-04-02

## Background

The equal-weight null experiment showed:
- The full engine is indistinguishable from equal weight (v2: Sharpe 1.247 vs 1.272; the v1 figure of 0.98 was a calculation asymmetry, see existential-experiment-v2.md)
- Risk management does NOT add statistically significant risk-adjusted value (Sharpe CI includes zero)
- Risk management provides modest tail protection (1.25pp drawdown improvement)

This research tests four alternative architectures to determine if the engine's components can be reconfigured to add value.

## Test 1: Equal Weight Baseline (Confirmation)

**Hypothesis:** Naive 1/N equal weight across 9 mega-cap stocks is the hardest-to-beat baseline.

### Results

| Metric | Equal Weight |
|-|-|
| Ann. Return | 25.71% |
| Ann. Volatility | 20.22% |
| Sharpe | 1.272 |
| Max Drawdown | -27.35% |
| CVaR (95%) | -10.34% |
| Recovery (worst DD) | 296 days |

**Confirmed.** This remains the baseline to beat. No strategy below improves on it in a statistically significant way on a risk-adjusted basis.

## Test 2: Factor TIMING Instead of Factor TILTING

**Hypothesis:** Instead of overweighting high-momentum stocks (which adds negative value), use the regime detector to time WHEN to have market exposure. Risk_on = 100% equity, risk_off = 60% equity / 40% cash, crisis = 30% equity / 70% cash. Cash earns the 10Y Treasury rate.

### Results

| Metric | Factor Timing | Equal Weight | Difference |
|-|-|-|-|
| Ann. Return | 19.75% | 25.71% | -5.96pp |
| Ann. Volatility | 16.18% | 20.22% | -4.04pp |
| Sharpe | 1.220 | 1.272 | -0.052 |
| Max Drawdown | -26.81% | -27.35% | +0.54pp |
| CVaR (95%) | -9.66% | -10.34% | +0.68pp |
| Recovery | 389 days | 296 days | -93 days worse |
| Avg Turnover | 17.8% | 0.0% | +17.8pp |

### Bootstrap 95% CI (Sharpe Difference: FT - EW)
- CI: [-0.298, +0.153]
- Median: -0.100
- Includes zero: YES

### Paired t-test
- t = -2.31, p = 0.023 (Factor Timing returns significantly LOWER)

### Regime Breakdown

| Regime | FT Mean Monthly | EW Mean Monthly | FT Sharpe | EW Sharpe | Periods |
|-|-|-|-|-|-|
| risk_on | 1.94% | 2.02% | 0.391 | 0.404 | 80 |
| risk_off | 0.54% | 2.11% | 0.118 | 0.285 | 18 |
| crisis | 1.02% | 2.51% | 0.370 | 0.362 | 10 |

### Interpretation

**Factor timing HURTS returns.** The regime detector successfully identifies risk_off periods, but the problem is that this market (2016-2026) recovered rapidly from every drawdown. Going to 60% equity during risk_off captured only 0.54% monthly vs 2.11% for staying fully invested. The strategy correctly reduced vol (-4pp) but sacrificed 6pp of annual return to do it.

The regime detector is NOT accurate enough for market timing. It identifies risk_off regimes, but the subsequent month still averaged +2.11% for full equity. The detector has too many false positives, it calls risk_off during what turn out to be buying opportunities.

**Critical issue:** Recovery took 389 days vs 296 days for equal weight. Factor timing WORSENED recovery because it reduced exposure precisely when the strongest bounces occurred.

**VERDICT: REJECT.** Factor timing destroys return without improving risk-adjusted performance. The regime detector is not precise enough for market timing on a monthly horizon.

## Test 3: Expanded Universe (Sector ETFs)

**Hypothesis A:** A more diverse universe (10 sector ETFs vs 9 individual mega-caps) may produce better risk-adjusted returns.

**Hypothesis B:** Sector momentum (12-1) may have more predictive power than stock momentum among correlated mega-caps.

### Results: Sector ETF Equal Weight

| Metric | Sector ETF EW | Stock EW | Difference |
|-|-|-|-|
| Ann. Return | 12.35% | 25.71% | -13.36pp |
| Ann. Volatility | 18.88% | 20.22% | -1.34pp |
| Sharpe | 0.654 | 1.272 | -0.618 |
| Max Drawdown | -36.36% | -27.35% | -9.01pp worse |

### Results: Sector ETF with Momentum Tilting

| Metric | Sector Mom | Sector EW | Difference |
|-|-|-|-|
| Ann. Return | 13.13% | 12.35% | +0.78pp |
| Sharpe | 0.703 | 0.654 | +0.049 |
| Max Drawdown | -34.88% | -36.36% | +1.48pp |
| Avg Turnover | 9.8% | 0.0% | +9.8pp |

### Momentum Information Coefficient Comparison

| Universe | Mean IC | IC Std | ICIR | t-stat | p-value | N |
|-|-|-|-|-|-|-|
| Sector ETFs (10) | 0.022 | 0.434 | 0.052 | 0.464 | 0.644 | 81 |
| Individual Stocks (9) | 0.052 | 0.462 | 0.112 | 1.157 | 0.250 | 107 |

### Interpretation

**Sector ETFs are dramatically worse.** The stock universe (AAPL, NVDA, AMZN, MSFT, etc.) outperformed because it is heavily tilted toward mega-cap tech, which dominated 2016-2026. Equal-weighting across ALL sectors forced equal allocation to energy (XLE), real estate (XLRE), and utilities (XLU), massive drags on performance.

**Sector momentum has LESS predictive power than stock momentum.** Mean IC is 0.022 for sectors vs 0.052 for stocks (both statistically insignificant). ICIR is 0.052 vs 0.112. Neither is tradeable, but stock momentum is at least directionally better.

**Survivorship caveat:** The stock universe has extreme survivorship bias (9 mega-cap winners chosen with hindsight). Sector ETFs are a more honest test. The 12.35% sector ETF return is closer to what a "no skill" diversified portfolio actually achieves.

**VERDICT: REJECT.** Switching to sector ETFs dramatically reduces returns (even after accounting for survivorship bias in the stock universe). Sector momentum has no predictive power (IC = 0.022, p = 0.644).

## Test 4: Crash-Buying Protocol as Standalone Strategy

**Hypothesis:** Hold equal weight normally. When VIX > 30, increase equity exposure by 20% (lever up). When VIX drops below 25, return to normal. This captures the well-documented "buy the crash" premium.

Two variants tested:
- **4a (Leverage):** Normal = 100% equity, VIX > 30 = 120% equity (borrow at 6% to lever up)
- **4b (Cash buffer):** Normal = 80% equity / 20% cash, VIX > 30 = 100% equity (deploy cash reserve)

### Results

| Metric | CrashBuy (Lever) | CrashBuy (Cash) | Equal Weight |
|-|-|-|-|
| Ann. Return | 25.48% | 21.21% | 25.71% |
| Ann. Volatility | 21.61% | 17.59% | 20.22% |
| Sharpe | 1.179 | 1.206 | 1.272 |
| Max Drawdown | -29.73% | -24.80% | -27.35% |
| CVaR (95%) | -11.25% | -9.05% | -10.34% |
| Recovery | 75 days | 73 days | 296 days |
| Avg Turnover | 2.2% | 2.2% | 0.0% |

### Bootstrap 95% CI (Sharpe Difference vs EW)

| Variant | CI Lower | CI Upper | Median | Zero? |
|-|-|-|-|-|
| CrashBuy Lever - EW | -0.116 | +0.016 | -0.043 | YES |
| CrashBuy Cash - EW | -0.087 | +0.060 | -0.006 | YES |

### Paired t-test

| Variant | t-stat | p-value | Sig? |
|-|-|-|-|
| CrashBuy Lever - EW | 0.563 | 0.575 | NO |
| CrashBuy Cash - EW | -3.401 | 0.001 | YES (lower returns) |

### Regime Breakdown (CrashBuy Lever)

| Regime | CB Mean Monthly | EW Mean Monthly | Periods |
|-|-|-|-|
| risk_on | 2.05% | 2.02% | 80 |
| risk_off | 1.89% | 2.11% | 18 |
| crisis | 2.53% | 2.51% | 10 |

### Interpretation

**The crash-buying leverage variant essentially matches equal weight.** +25.48% vs +25.71% return. The extra 20% leverage during high-VIX periods captures the crash recovery, but the borrowing cost (6%) and higher vol mostly offset the gains.

**The cash buffer variant sacrifices return for stability.** Holding 20% cash normally costs 4.5pp annual return, and the crash-buying protocol does not fully recoup this. However, it achieves the BEST max drawdown (-24.80%) and dramatically faster recovery (73 days vs 296 days).

**The recovery time improvement is genuine and large.** Both crash-buying variants recover in ~75 days vs 296 days for equal weight. This is because they increase exposure at the bottom of crashes, participating more in the recovery.

**Neither variant improves Sharpe ratio significantly.** Bootstrap CIs include zero.

**VERDICT: INVESTIGATE FURTHER (Cash Buffer variant only).** The cash buffer variant trades 4.5pp annual return for 2.5pp less drawdown and 4x faster recovery. This is not alpha, it is a risk preference trade-off. For an investor who cannot stomach 296-day drawdowns, this is valuable. For an investor with a long horizon and no liquidity needs, the leverage variant is strictly worse than staying fully invested.

## Summary Table

| Strategy | Sharpe | vs EW | Stat Sig? | Verdict |
|-|-|-|-|-|
| Equal Weight (baseline) | 1.272 | n/a | n/a | BASELINE |
| Factor Timing (regime) | 1.220 | -0.052 | NO | REJECT |
| Sector ETF EW | 0.654 | -0.618 | NO | REJECT |
| Sector ETF Momentum | 0.703 | -0.569 | NO | REJECT |
| Crash Buy (leverage) | 1.179 | -0.093 | NO | REJECT |
| Crash Buy (cash buffer) | 1.206 | -0.066 | NO | INVESTIGATE |

## Conclusions

1. **Nothing beats naive equal weight on 9 mega-cap stocks over 2016-2026.** This result is humbling but not surprising, it is consistent with the academic literature showing 1/N is extremely hard to beat in concentrated portfolios of liquid large-caps.

2. **The regime detector has insufficient precision for market timing.** It correctly identifies elevated risk, but the market recovers too quickly for a monthly rebalance to capture the benefit. The false positive rate is too high.

3. **Sector momentum is weaker than stock momentum.** Both are statistically insignificant, but sector rotation adds no value.

4. **Crash-buying works mechanically (faster recovery) but does not improve risk-adjusted returns.** The cash buffer variant is the only strategy worth further investigation, and only for investors with specific drawdown tolerance constraints.

5. **The honest conclusion:** For a long-horizon investor, the optimal strategy from this analysis is 100% equal weight in quality mega-caps with zero signal tilting and zero market timing. The engine's complexity adds cost without adding return.

## Important Caveats

- **Survivorship bias:** The 9-stock universe was selected with hindsight. Real equal-weight performance on a 2016-era selection would be lower. The 25.71% return overstates what was achievable.
- **Regime analysis:** Only 10 crisis periods and 18 risk_off periods in 10 years. The sample is too small for confident regime-conditional conclusions.
- **One market regime:** 2016-2026 was dominated by US mega-cap tech outperformance. Results may not generalize to regimes where tech underperforms.
- **Transaction costs:** All strategies use the same spread + sqrt impact model. Crash-buying during high-VIX periods may face wider spreads in practice.
