# Comprehensive Momentum Lookback Study

**Date:** 2026-04-02
**Status:** COMPREHENSIVE STUDY

## 1. Signal Description and Hypothesis

The standard momentum signal uses 12-month lookback with 1-month skip (12-1). The factor crowding study showed a 3-month lookback (3-1) delivering 5x the Sharpe of 12-1 on a five-year long-short test. This study systematically tests lookbacks of 2, 3, 4, 6, 9, and 12 months across both US (9 stocks) and India (20 NSE stocks) universes using walk-forward validation with realistic transaction costs.

**Hypothesis:** Shorter momentum lookbacks (2-4 months) capture faster mean-reverting momentum that is more robust in concentrated portfolios, at the cost of higher turnover. The optimal lookback balances signal strength against transaction costs.

**Academic support:** Novy-Marx (2012) showed 7-12 month intermediate momentum is the true anomaly in US markets. However, Chui, Titman, Wei (2010) found shorter lookbacks work better in emerging markets due to higher retail participation and slower information diffusion. Goyal and Wahal (2015) find 3-6 month momentum dominates in non-US markets.

## 2. Data and Methodology

**US Universe:** AAPL, GOOGL, AMZN, NVDA, JNJ, KO, BRK-B, COST, MSFT (benchmark: VOO)
**India Universe:** 20 NSE stocks (benchmark: Nifty 50)
**US Data Period:** 2015-01-02 to 2026-03-31 (2827 trading days)
**India Data Period:** 2015-01-01 to 2026-03-30 (2776 trading days)

**Walk-forward design:**
- Expanding training window (minimum 252 days)
- 21-day (1-month) out-of-sample test periods
- Monthly rebalancing with turnover costs
- Momentum signal tilts equal-weight portfolio (tilt_strength=0.5)
- Weight bounds: [2%, 40%]
- All lookback variants skip most recent 21 trading days (1 month)

**Transaction cost model:**
- Spread cost: 5.0 bps each way
- Market impact: 3.0 bps each way (sqrt model)
- Total round-trip: 16.0 bps
- Applied to full turnover (two-way)

**No lookahead bias:** All signals computed on training data only. Regime detection uses only past VIX. Walk-forward ensures strict temporal separation.

## 3. US Market Results

### 3.1 Walk-Forward Performance Summary

| Lookback | WF Sharpe | Ann. Return | Ann. Alpha | Ann. Turnover | Cost (%) | Net Alpha | Max DD | t-stat | p-value |
|-|-|-|-|-|-|-|-|-|-|
| 2-1 | 1.3416 | 22.84% | 8.47% | 1.26x | 0.10% | 8.37% | -25.83% | 2.77 | 0.0065 |
| 3-1 | 1.3316 | 22.77% | 8.40% | 1.04x | 0.08% | 8.32% | -26.08% | 2.80 | 0.0060 |
| 4-1 | 1.3291 | 22.84% | 8.47% | 0.90x | 0.07% | 8.40% | -25.80% | 2.81 | 0.0058 |
| 6-1 | 1.3780 | 24.08% | 9.71% | 0.73x | 0.06% | 9.65% | -25.61% | 3.32 | 0.0012 |
| 9-1 | 1.3644 | 23.93% | 9.57% | 0.56x | 0.04% | 9.52% | -24.99% | 3.24 | 0.0016 |
| 12-1 | 1.3657 | 24.09% | 9.43% | 0.49x | 0.04% | 9.39% | -25.25% | 3.16 | 0.0020 |

### 3.2 Bootstrap 95% Confidence Intervals on Sharpe

| Lookback | Point Sharpe | 95% CI Lower | 95% CI Upper | CI Width |
|-|-|-|-|-|
| 2-1 | 1.3416 | 0.7285 | 1.9832 | 1.2547 |
| 3-1 | 1.3316 | 0.7150 | 1.9626 | 1.2476 |
| 4-1 | 1.3291 | 0.7067 | 1.9560 | 1.2493 |
| 6-1 | 1.3780 | 0.7598 | 2.0101 | 1.2503 |
| 9-1 | 1.3644 | 0.7385 | 2.0079 | 1.2694 |
| 12-1 | 1.3657 | 0.7384 | 2.0086 | 1.2702 |

### 3.3 Sharpe Difference vs 12-1 Baseline (Bootstrap)

| Lookback | Sharpe Diff | 95% CI Lower | 95% CI Upper | P(beats 12-1) | Significant? |
|-|-|-|-|-|-|
| 2-1 | -0.0241 | -0.9311 | 0.8596 | 46.8% | NO |
| 3-1 | -0.0341 | -0.9210 | 0.8473 | 46.1% | NO |
| 4-1 | -0.0366 | -0.9240 | 0.8372 | 47.4% | NO |
| 6-1 | 0.0123 | -0.8680 | 0.9019 | 50.5% | NO |
| 9-1 | -0.0013 | -0.9030 | 0.9120 | 50.0% | NO |

### 3.4 Information Coefficient Analysis

| Lookback | Mean IC | IC Std | ICIR | % Positive | n |
|-|-|-|-|-|-|
| 2-1 | 0.0489 | 0.4317 | 0.1133 | 54.9% | 122 |
| 3-1 | 0.0423 | 0.4572 | 0.0926 | 50.8% | 122 |
| 4-1 | 0.0130 | 0.4598 | 0.0282 | 46.7% | 122 |
| 6-1 | 0.0434 | 0.4545 | 0.0956 | 51.6% | 122 |
| 9-1 | 0.0605 | 0.4600 | 0.1316 | 59.0% | 122 |
| 12-1 | 0.0596 | 0.4657 | 0.1281 | 53.7% | 121 |

### 3.5 Regime-Conditional Performance (US)

| Lookback | Regime | Months | Avg Alpha | Sharpe | Win Rate |
|-|-|-|-|-|-|
| 2-1 | crisis | 6 | -2.5212% | 3.1261 | 16.7% |
| 2-1 | risk_off | 31 | 0.1496% | 1.7648 | 48.4% |
| 2-1 | risk_on | 85 | 0.9690% | 1.4375 | 71.8% |
| 3-1 | crisis | 6 | -2.4101% | 3.2494 | 16.7% |
| 3-1 | risk_off | 31 | 0.1104% | 1.7497 | 45.2% |
| 3-1 | risk_on | 85 | 0.9695% | 1.4284 | 74.1% |
| 4-1 | crisis | 6 | -2.1271% | 3.2502 | 16.7% |
| 4-1 | risk_off | 31 | 0.1348% | 1.8050 | 41.9% |
| 4-1 | risk_on | 85 | 0.9488% | 1.3991 | 70.6% |
| 6-1 | crisis | 6 | -1.9064% | 3.3828 | 16.7% |
| 6-1 | risk_off | 31 | 0.2269% | 1.8561 | 48.4% |
| 6-1 | risk_on | 85 | 1.0203% | 1.4856 | 74.1% |
| 9-1 | crisis | 6 | -2.0575% | 3.2242 | 16.7% |
| 9-1 | risk_off | 31 | 0.2063% | 1.8566 | 41.9% |
| 9-1 | risk_on | 85 | 1.0273% | 1.4606 | 71.8% |
| 12-1 | crisis | 6 | -1.9325% | 3.3823 | 16.7% |
| 12-1 | risk_off | 30 | 0.2148% | 1.7334 | 40.0% |
| 12-1 | risk_on | 84 | 1.0016% | 1.4898 | 73.8% |

## 4. India Market Results

### 4.1 Walk-Forward Performance Summary

| Lookback | WF Sharpe | Ann. Return | Ann. Alpha | Ann. Turnover | Cost (%) | Net Alpha | Max DD | t-stat | p-value |
|-|-|-|-|-|-|-|-|-|-|
| 2-1 | 1.1795 | 19.88% | 7.89% | 1.39x | 0.11% | 7.78% | -37.26% | 4.32 | 0.0000 |
| 3-1 | 1.1571 | 19.53% | 7.54% | 1.09x | 0.09% | 7.45% | -37.74% | 4.44 | 0.0000 |
| 4-1 | 1.1584 | 19.61% | 7.62% | 0.97x | 0.08% | 7.54% | -38.12% | 4.31 | 0.0000 |
| 6-1 | 1.1876 | 20.26% | 8.27% | 0.79x | 0.06% | 8.20% | -37.87% | 4.72 | 0.0000 |
| 9-1 | 1.1906 | 20.26% | 8.27% | 0.66x | 0.05% | 8.21% | -37.79% | 4.74 | 0.0000 |
| 12-1 | 1.2322 | 21.00% | 8.84% | 0.55x | 0.04% | 8.80% | -38.04% | 5.23 | 0.0000 |

### 4.2 Bootstrap 95% CI on Sharpe (India)

| Lookback | Point Sharpe | 95% CI Lower | 95% CI Upper |
|-|-|-|-|
| 2-1 | 1.1795 | 0.5418 | 1.8501 |
| 3-1 | 1.1571 | 0.5254 | 1.8074 |
| 4-1 | 1.1584 | 0.5298 | 1.8345 |
| 6-1 | 1.1876 | 0.5501 | 1.8658 |
| 9-1 | 1.1906 | 0.5570 | 1.8512 |
| 12-1 | 1.2322 | 0.5916 | 1.9013 |

### 4.3 Information Coefficient (India)

| Lookback | Mean IC | ICIR | % Positive |
|-|-|-|-|
| 2-1 | -0.0103 | -0.0326 | 52.5% |
| 3-1 | -0.0211 | -0.0698 | 50.0% |
| 4-1 | -0.0173 | -0.0570 | 50.0% |
| 6-1 | 0.0202 | 0.0670 | 53.3% |
| 9-1 | 0.0017 | 0.0059 | 47.5% |
| 12-1 | 0.0151 | 0.0515 | 48.7% |

### 4.4 Regime-Conditional Performance (India)

| Lookback | Regime | Months | Avg Alpha | Sharpe | Win Rate |
|-|-|-|-|-|-|
| 2-1 | risk_on | 120 | 0.5805% | 1.1204 | 67.5% |
| 3-1 | risk_on | 120 | 0.5578% | 1.0977 | 65.0% |
| 4-1 | risk_on | 120 | 0.5628% | 1.1031 | 65.0% |
| 6-1 | risk_on | 120 | 0.6058% | 1.1408 | 68.3% |
| 9-1 | risk_on | 120 | 0.6094% | 1.1301 | 65.8% |
| 12-1 | risk_on | 118 | 0.6510% | 1.1692 | 66.1% |

## 5. Signal Correlation Analysis

Cross-sectional Spearman rank correlations between lookback variants and existing signals (computed at final date of US data):

```
         mom_2m  mom_3m  mom_4m  mom_6m  mom_9m  mom_12m     rsi   trend
mom_2m   1.0000  0.9667  0.8333  0.8000  0.5667   0.4500 -0.6833  0.9271
mom_3m   0.9667  1.0000  0.7833  0.7500  0.5667   0.4833 -0.6667  0.8491
mom_4m   0.8333  0.7833  1.0000  0.8333  0.4833   0.3667 -0.5500  0.7365
mom_6m   0.8000  0.7500  0.8333  1.0000  0.8167   0.7167 -0.3833  0.7885
mom_9m   0.5667  0.5667  0.4833  0.8167  1.0000   0.8833 -0.3167  0.5285
mom_12m  0.4500  0.4833  0.3667  0.7167  0.8833   1.0000 -0.1000  0.4159
rsi     -0.6833 -0.6667 -0.5500 -0.3833 -0.3167  -0.1000  1.0000 -0.6845
trend    0.9271  0.8491  0.7365  0.7885  0.5285   0.4159 -0.6845  1.0000
```

**Key observations:**

- 2-1 vs 12-1 correlation: 0.4500
- 3-1 vs 12-1 correlation: 0.4833
- 4-1 vs 12-1 correlation: 0.3667
- 6-1 vs 12-1 correlation: 0.7167
- 9-1 vs 12-1 correlation: 0.8833
- 2-1 vs RSI: -0.6833, vs Trend: 0.9271
- 3-1 vs RSI: -0.6667, vs Trend: 0.8491
- 4-1 vs RSI: -0.5500, vs Trend: 0.7365
- 6-1 vs RSI: -0.3833, vs Trend: 0.7885
- 9-1 vs RSI: -0.3167, vs Trend: 0.5285
- 12-1 vs RSI: -0.1000, vs Trend: 0.4159

## 6. Turnover and Transaction Cost Sensitivity

| Lookback | Monthly Turnover | Annual Turnover | Annual Cost (8bps RT) | Annual Cost (16bps RT) | Annual Cost (30bps RT) |
|-|-|-|-|-|-|
| 2-1 | 0.1048 | 1.26x | 0.10% | 0.20% | 0.38% |
| 3-1 | 0.0866 | 1.04x | 0.08% | 0.17% | 0.31% |
| 4-1 | 0.0752 | 0.90x | 0.07% | 0.14% | 0.27% |
| 6-1 | 0.0609 | 0.73x | 0.06% | 0.12% | 0.22% |
| 9-1 | 0.0463 | 0.56x | 0.04% | 0.09% | 0.17% |
| 12-1 | 0.0412 | 0.49x | 0.04% | 0.08% | 0.15% |

**Interpretation:** Shorter lookbacks produce higher turnover, but the incremental cost 
is modest for liquid mega-caps. Even at 30bps round-trip (pessimistic for our universe), 
the cost difference between 3-1 and 12-1 is typically under 50bps annually.

## 7. Net-of-Cost Ranking

After applying realistic transaction costs (spread + sqrt market impact):

| Rank | Lookback | Gross Alpha | Cost | Net Alpha | Net Sharpe |
|-|-|-|-|-|-|
| 1 | 6-1 | 9.71% | 0.06% | 9.65% | 1.3778 |
| 2 | 9-1 | 9.57% | 0.04% | 9.52% | 1.3642 |
| 3 | 12-1 | 9.43% | 0.04% | 9.39% | 1.3655 |
| 4 | 4-1 | 8.47% | 0.07% | 8.40% | 1.3288 |
| 5 | 2-1 | 8.47% | 0.10% | 8.37% | 1.3412 |
| 6 | 3-1 | 8.40% | 0.08% | 8.32% | 1.3313 |

## 8. Academic Context: Why Shorter Momentum Works

### For US Markets
- Novy-Marx (2012) showed intermediate-horizon (7-12 month) momentum is the classic anomaly
- However, our universe is 9 mega-cap stocks, NOT a broad cross-section
- In concentrated portfolios, shorter lookbacks capture idiosyncratic mean-reversion patterns
- Post-2020 market structure changes (retail, options gamma) create faster momentum cycles

### For India / Emerging Markets
- Chui, Titman, Wei (2010): momentum is weaker in Asia but shorter lookbacks help
- Goyal and Wahal (2015): 3-6 month momentum dominates in non-US markets
- Higher retail participation creates faster price discovery cycles
- FII flow-driven markets exhibit momentum at 2-4 month horizons
- Circuit breaker mechanisms in India truncate extreme moves, favoring shorter windows

## 9. Risk Factors and Caveats

1. **Small universe bias:** With 9 US stocks, cross-sectional momentum signals have limited
   dispersion. Results may not generalize to broader universes.
2. **Survivorship bias:** All tickers are current large-caps. No delisted stocks in backtest.
3. **Regime dependency:** Results are regime-conditional. See Section 3.5 for breakdown.
4. **Overfitting risk:** Testing 6 lookbacks introduces multiple testing concern.
   Bonferroni-adjusted significance level: p < 0.0083
5. **Transaction cost assumptions:** We use 8bps total (spread + impact). Actual costs for mega-caps are likely lower (1-3 bps spread), making shorter lookbacks more attractive.
6. **Equal-weight base:** Results use equal-weight + momentum tilt, not HRP. Full engine integration may produce different results due to HRP correlation structure.

### Bonferroni Multiple Testing Correction

Testing 6 lookbacks requires adjusted p-value threshold: 0.0083

| Lookback | Raw p-value | Bonferroni significant? |
|-|-|-|
| 2-1 | 0.0065 | YES |
| 3-1 | 0.0060 | YES |
| 4-1 | 0.0058 | YES |
| 6-1 | 0.0012 | YES |
| 9-1 | 0.0016 | YES |
| 12-1 | 0.0020 | YES |

## 10. Factor Crowding Claim vs Reality

The factor crowding study reported 3-1 momentum delivering 5x higher Sharpe (0.864) vs 12-1 (0.164). **This study
could not reproduce that claim.** The comprehensive walk-forward results show:

- All lookback variants produce Sharpe ratios between 1.16 and 1.38, tightly clustered
- No lookback variant is statistically distinguishable from 12-1 (bootstrap Sharpe difference CIs
  all straddle zero, P(beats 12-1) ranges from 46-51%)
- The earlier result was likely an artifact of different methodology (simple backtest vs walk-forward),
  different time period, or different portfolio construction

**This is a null finding. The lookback parameter does not matter much for our universe.**

## 11. Conclusion and Recommendation

### US: Best lookback is **6-1** (marginal)
- Net annual alpha: 9.65% (vs 9.39% for 12-1, a 26bps difference)
- Walk-forward Sharpe: 1.3780 (vs 1.3657 for 12-1)
- Sharpe 95% CI: [0.7598, 2.0101]
- The improvement over 12-1 is **NOT statistically significant** (P(better) = 50.5%)
- Annual turnover: 0.73x (vs 0.49x for 12-1)

### India: Best lookback is **12-1**
- Net annual alpha: 8.80%, the current default wins
- Walk-forward Sharpe: 1.2322, highest of all variants
- Shorter lookbacks uniformly underperform in India, contradicting the EM hypothesis
- This may reflect that our India universe (20 Nifty stocks) behaves like developed-market large caps

### IC Analysis Warning
- All ICIR values are below 0.15 (weak signal quality across ALL lookbacks)
- India IC is near zero or negative for short lookbacks, the signal has no cross-sectional predictive power
- This means momentum is contributing through portfolio-level beta timing, not stock selection

### What Actually Matters
The regime-conditional analysis reveals the real story:
- **Risk-on (70% of months):** All lookbacks produce ~1.0% monthly alpha, ~72% win rate
- **Risk-off (25% of months):** All lookbacks produce ~0.15% monthly alpha, ~45% win rate
- **Crisis (5% of months):** ALL lookbacks produce NEGATIVE alpha (-1.9% to -2.5%)
- The crisis regime alpha loss is nearly identical across lookbacks

This means: **the lookback parameter is a second-order effect.** The first-order effect is regime
detection quality. Improving crisis detection would matter 10x more than optimizing lookback.

### Verdict: **REJECT (the hypothesis that lookback matters)**

The data does not support changing from 12-1 to any shorter lookback:
1. No statistically significant Sharpe improvement at any alternative lookback
2. India performs best with the current 12-1
3. Shorter lookbacks increase turnover without compensating alpha
4. The 6-1 variant shows a marginal gross alpha advantage in US (26bps) that is economically
   insignificant and statistically indistinguishable from noise

### Actionable Recommendations
1. **Keep MOMENTUM_LOOKBACK = 252** (12-1). No change justified.
2. **Prioritize regime detection improvement** over signal parameter tuning. Crisis periods
   destroy alpha uniformly regardless of lookback.
3. If we want to add value through momentum, add a **dual-momentum blend** (6-1 + 12-1 averaged)
   as a robustness measure, not a performance improvement. This is a hedging strategy, not alpha.
4. The IC analysis confirms momentum is a weak cross-sectional signal in concentrated portfolios.
   Our alpha comes from the full signal composite + HRP, not momentum alone.

separation. No future information used in signal construction. The null finding that lookback does
not matter is itself valuable, it means our current implementation is not leaving money on the table.*

## 12. Independent Reproduction on a 10-Year Window

A second run repeated the long-short construction from the factor crowding study (long top 3, short bottom 3 by momentum rank, monthly rebalance, no costs) on the same nine stocks over April 2016 to April 2026 instead of the five-year window used there.

| Variant | L/S Sharpe, 10 years | L/S Sharpe, 5 years (factor crowding study) |
|-|-|-|
| 3-1 | 0.158 | 0.864 |
| 12-1 | 0.225 | 0.164 |

The five-year 3-1 result does not reproduce on the longer sample. Both lookbacks are statistically zero over ten years.

The same run embedded 24 lookback and skip variants (6 lookbacks x 4 skips) in the full walk-forward portfolio (HRP base, 50% tilt, position limits, 5 bps spread plus square-root impact costs). This differs from sections 3 and 4 above, which tilt an equal-weight base, so the Sharpe levels are not comparable across the two tables.

| Variant | WF Sharpe | Alpha t-stat | Monthly turnover |
|-|-|-|-|
| 9m-0d (best of 24) | 1.036 | 3.837 | 0.045 |
| 3m-5d | 1.035 | 3.610 | 0.081 |
| 12m-1d (production) | 0.966 | 3.461 | 0.041 |
| 3m-1d | 0.975 | 3.291 | 0.083 |
| Equal weight, no signal | 1.011 | n/a | 0.000 |

All 24 variants fall between 0.937 and 1.036 walk-forward Sharpe. Equal weight with no momentum tilt scored 1.011, above the production 12-1 tilt (0.966) and the 3-1 tilt (0.975). Split-half stability: 3-1 first half 0.988, second half 0.747 (24.4% decay); 12-1 first half 0.982, second half 1.172. The best in-sample variant (9m-0d) decayed most, 1.059 to 0.779. Cross-sectional correlation between the 3-1 and 12-1 signals averaged 0.518 (std 0.372). Correlation between 3-1 momentum and one-week reversal was -0.011, so 3-1 is not reversal in disguise.

Stress-period alpha of the momentum tilt: COVID (February to April 2020) 3-1 +13.7%, 12-1 +12.3%; 2022 rate hikes 3-1 -1.5%, 12-1 +1.5%; 2023 SVB 3-1 +8.8%, 12-1 +7.9%.

Conclusion of the reproduction: the lookback does not matter, and the momentum tilt at any lookback does not beat equal weight in this universe.
