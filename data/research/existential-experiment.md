# Equal-Weight Null Experiment (v1): Does the Risk Management Stack Add Value?

**Date:** 2026-04-02
**Script:** `data/research/existential_experiment.py`
**Superseded by:** `existential-experiment-v2.md` for the US Strategy C figure. The Strategy C Sharpe reported here (0.98) came from a different calculation path than A and B and is a measurement artifact; the corrected US figure is 1.247. The A and B figures below stand.

## Hypothesis

An earlier lookback sweep showed that momentum tilts do not beat naive equal weight (10-year walk-forward Sharpe 0.966 for the production tilt versus 1.011 for 1/N). This experiment isolates the question: does the risk management stack alone (vol targeting, sector limits, position limits, CVaR constraint, regime-adaptive rebalancing) add measurable value on top of equal weight?

## Methodology

Three strategies compared head-to-head on identical data and time periods:

**Strategy A (Naive Equal Weight):** 1/N weights, monthly rebalance, realistic transaction costs. This is the baseline anyone can replicate with a brokerage account.

**Strategy B (Equal Weight + Risk Management):** Start with 1/N weights, then apply the risk management stack in production order:
1. Vol targeting (target 15% US / 20% India, 63-day window, scalar clipped 0.5 to 1.5)
2. Sector exposure limits (40% max per sector)
3. Position limits (25% max single stock, 1.5 max portfolio beta)
4. CVaR constraint (3% max monthly CVaR at 95% confidence)
5. Regime-adaptive rebalancing frequency (crisis weekly, risk_off biweekly, risk_on monthly)
6. Same transaction cost model as A (spread 5 bps plus square-root impact model)

**Strategy C (Full Engine):** All signals plus HRP weights, signal tilting, and the full risk management stack.

**Data:** Maximum available history via yfinance (about 10 years). Walk-forward with a 252-day minimum training window and monthly test periods. Transaction costs use spread plus square-root market impact (spread_bps=5, impact_k=0.1).

**Statistical tests:** Bootstrap 95% CI on the Sharpe difference (10,000 resamples on monthly returns). Paired t-test on monthly return differences as a secondary check.

## US (9 stocks) Results

**Test period:** 108 monthly periods

| Metric | A: Equal Weight | B: EW + Risk Mgmt |
|-|-|-|
| Ann. Return (after costs) | 25.71% | 22.43% |
| Ann. Volatility | 20.22% | 17.95% |
| Sharpe Ratio | 1.27 | 1.25 |
| Max Drawdown | -27.35% | -26.10% |
| Monthly CVaR (95%) | -10.34% | -8.99% |
| Avg Turnover per Rebalance | 0.00% | 1.64% |
| Monthly Return Corr (A vs B) | 0.98 | n/a |

Strategy C (full engine) in this run: 22.47% annual return, -25.89% max drawdown, Sharpe 0.98 as originally computed. See the note at the top: the 0.98 is not comparable with A and B and was corrected to 1.247 in v2.

### Stress Tests

| Event | A: Return | A: Worst DD | B: Return | B: Worst DD |
|-|-|-|-|-|
| COVID crash | -26.23% | -26.23% | -26.10% | -26.10% |
| 2022 bear market | -25.25% | -26.87% | -21.87% | -23.91% |

### Bootstrap 95% CI on Sharpe Difference (10,000 resamples)

| Comparison | CI Lower | CI Upper | Median Diff | Includes Zero? |
|-|-|-|-|-|
| B - A | -0.1832 | 0.1317 | -0.0226 | YES |

### Paired t-test on Monthly Return Differences

| Comparison | t-statistic | p-value | Significant (p<0.05)? |
|-|-|-|-|
| A vs B | 2.0673 | 0.0411 | YES |

The t-test is on mean return, not risk-adjusted return. B has lower volatility by construction, so a lower mean return is expected; the bootstrap on Sharpe differences is the relevant test.

## India (20 stocks) Results

**Test period:** 108 monthly periods

| Metric | A: Equal Weight | B: EW + Risk Mgmt |
|-|-|-|
| Ann. Return (after costs) | 19.94% | 18.15% |
| Ann. Volatility | 16.62% | 16.03% |
| Sharpe Ratio | 1.20 | 1.13 |
| Max Drawdown | -37.14% | -36.02% |
| Monthly CVaR (95%) | -10.49% | -10.44% |
| Avg Turnover per Rebalance | 0.00% | 1.94% |
| Monthly Return Corr (A vs B) | 0.99 | n/a |

Strategy C (full engine) in this run: 17.75% annual return, -35.89% max drawdown, Sharpe 1.12 as originally computed, with the same calculation asymmetry as the US figure. India has not been re-run under the v2 framework.

### Stress Tests

| Event | A: Return | A: Worst DD | B: Return | B: Worst DD |
|-|-|-|-|-|
| COVID crash | -36.97% | -36.97% | -35.95% | -35.95% |
| 2022 bear market | 6.85% | -13.39% | 4.31% | -13.37% |

### Bootstrap 95% CI on Sharpe Difference (10,000 resamples)

| Comparison | CI Lower | CI Upper | Median Diff | Includes Zero? |
|-|-|-|-|-|
| B - A | -0.1226 | 0.0542 | -0.0297 | YES |

### Paired t-test on Monthly Return Differences

| Comparison | t-statistic | p-value | Significant (p<0.05)? |
|-|-|-|-|
| A vs B | 1.6612 | 0.0996 | NO |

## Review Corrections

An independent re-run reproduced A and B exactly (US: A 1.2716, B 1.2497, CI [-0.1832, +0.1317]). The following corrections were recorded:

1. **Recovery time.** The original report claimed B recovered from its worst drawdown in 95 days versus 296 for A. Those figures come from different episodes: A's worst drawdown was the 2022 bear market, B's was COVID. On the same event (COVID) A recovered in 67 trading days and B in 84, so B was about 25% slower, because vol targeting cuts exposure during the rebound. The recovery-time claim is withdrawn.
2. **Autocorrelation.** Ljung-Box on monthly returns: A p = 0.287 (lag 1), 0.445 (lag 12); B p = 0.177, 0.127. No significant autocorrelation, so the iid bootstrap is appropriate. A block bootstrap (block size 3) gives a CI of [-0.2084, +0.1403] for B - A, slightly wider, same conclusion.
3. **Power.** Detecting a Sharpe difference of 0.02 at 80% power and 5% significance needs on the order of 78,000 monthly observations; there are 108. The experiment can show the difference is small, not which strategy is better.
4. **Vol targeting mechanics.** A 15% target against roughly 20% realized volatility scales exposure to about 0.75 on average (clipped to 0.5 to 1.5). Most of the return gap between A and B is that exposure reduction, which a fixed 75/25 equity-cash split would reproduce without any model.
5. **Regime-conditional Sharpe.** Low VIX (<20): A 4.23, B 4.35. High VIX (>=20): A -1.00, B -0.97. Both differences are within noise.
6. **Decay.** First-half versus second-half Sharpe: A 1.622 to 1.193, B 1.561 to 1.192. Both decay; risk management does not prevent it.
7. **Strategy C comparison.** C's Sharpe came from the walk-forward function's internal calculation while A and B used daily portfolio values, and C's daily series was synthesized from monthly returns. v2 rebuilt all three strategies on one code path.

## Conclusion

Risk management reduces volatility (20.22% to 17.95% in the US) and trims maximum drawdown by about 1.25 percentage points. The Sharpe difference against naive equal weight is -0.02 (US) and -0.07 (India), with bootstrap intervals that include zero in both markets. The 2022 bear market is the one episode where the overlay both lost less and drew down less; one episode is not a pattern. Vol targeting was later removed from the engine; the sector, single-name, beta and CVaR caps remain as risk limits without any return claim attached.
