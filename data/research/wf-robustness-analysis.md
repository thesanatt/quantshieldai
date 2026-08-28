# Walk-Forward Robustness Analysis

Generated: 2026-04-01 20:32:28

## Methodology

Three robustness dimensions tested for BOTH US and India engines:

1. **Lookback window sensitivity**: 126d (6mo) / 189d (9mo) / 252d (12mo, current) / 315d (15mo) / 378d (18mo)
   - Rebalance fixed at 21 days (monthly)
   - Tests whether momentum/vol-adj-momentum lookback period is cherry-picked

2. **Rebalance frequency sensitivity**: 10d (biweekly) / 21d (monthly, current) / 42d (bimonthly)
   - Lookback fixed at 252 days (12 months)
   - Tests whether rebalance frequency is cherry-picked

3. **Monte Carlo weight perturbation**: 100 trials
   - Each regime weight (risk_on, risk_off, crisis) independently perturbed by U(-20%, +20%)
   - Renormalized to sum=1 after perturbation
   - Tests whether alpha depends on exact weight choices

All results are **walk-forward (out-of-sample)** with 10bps transaction costs per leg.
Alpha = portfolio total return minus benchmark total return (VOO for US, Nifty 50 for India).

## US Engine (VOO benchmark)

### A. Lookback Window Sensitivity

| Lookback | Alpha (%) | Sharpe | Max DD (%) | Win Rate (%) | t-stat | p-value | Sig? |
|-|-|-|-|-|-|-|-|
| 126d (6mo) | 83.89 | 1.08 | -22.06 | 61.4 | 1.389 | 0.1693 | NO |
| 189d (9mo) | 91.58 | 1.09 | -22.59 | 67.1 | 1.5154 | 0.1342 | NO |
| 252d (12mo) * | 81.71 | 1.05 | -22.91 | 64.3 | 1.3423 | 0.1839 | NO |
| 315d (15mo) | 59.18 | 0.92 | -23.42 | 62.7 | 1.3351 | 0.1864 | NO |
| 378d (18mo) | 62.21 | 0.96 | -23.53 | 65.6 | 1.4521 | 0.1514 | NO |

\* = current production configuration

**Alpha range:** 59.18% to 91.58% (spread: 32.40pp)
**Assessment:** All 5 lookback windows produce positive alpha. ROBUST to lookback choice.

### B. Rebalance Frequency Sensitivity

| Rebalance | Alpha (%) | Sharpe | Max DD (%) | Win Rate (%) | t-stat | p-value | Sig? |
|-|-|-|-|-|-|-|-|
| 10d | 72.59 | 1.0 | -23.34 | 58.1 | 1.3016 | 0.1951 | NO |
| 21d * | 81.71 | 1.05 | -22.91 | 64.3 | 1.3423 | 0.1839 | NO |
| 42d | 91.9 | 1.08 | -22.86 | 71.4 | 1.8598 | 0.0716 | NO |

**Alpha range:** 72.59% to 91.90% (spread: 19.31pp)
**Assessment:** All rebalance frequencies produce positive alpha. ROBUST to frequency choice.

### C. Summary Grid (3x3)

Cell format: Alpha (%) / Sharpe

| Lookback \ Rebalance | 10d (biweekly) | 21d (monthly) | 42d (bimonthly) |
|-|-|-|-|
| 189d (9mo) | 80.54 / 1.04 | 91.58 / 1.09 | 88.28 / 1.08 |
| 252d (12mo) | 72.59 / 1.0 | 81.71 / 1.05 ** | 91.9 / 1.08 |
| 315d (15mo) | 58.09 / 0.89 | 59.18 / 0.92 | 54.06 / 0.92 |

\*\* = current production configuration

**Grid cells with positive alpha:** 9/9
**Grid alpha range:** 54.06% to 91.90%
**Assessment:** Alpha is positive across ALL grid cells. Engine is ROBUST to parameter choice.

### D. Monte Carlo Weight Perturbation

- **Trials:** 100
- **Perturbation:** +/-20% uniform on each signal weight within each regime, renormalized
- **Baseline alpha:** 81.71%

| Metric | Value |
|-|-|
| Mean alpha | 81.64% |
| Std dev alpha | 1.31% |
| 5th percentile | 79.63% |
| 95th percentile | 83.91% |
| Min alpha | 78.27% |
| Max alpha | 84.7% |
| % trials with positive alpha | 100.0% |
| % trials within 2pp of base | 85.0% |
| Sign flips (vs baseline) | 0/100 |
| Mean Sharpe | 1.05 |
| Std Sharpe | 0.0 |

**VERDICT:** Alpha is **ROBUST** to weight perturbation. 100.0% of perturbations produce positive alpha.

## India Engine (Nifty 50 benchmark)

### A. Lookback Window Sensitivity

| Lookback | Alpha (%) | Sharpe | Max DD (%) | Win Rate (%) | t-stat | p-value | Sig? |
|-|-|-|-|-|-|-|-|
| 126d (6mo) | 71.54 | 1.56 | -14.51 | 65.2 | 2.2602 | 0.027 | YES |
| 189d (9mo) | 67.29 | 1.55 | -14.27 | 63.8 | 2.118 | 0.0378 | YES |
| 252d (12mo) * | 81.49 | 1.6 | -14.45 | 62.3 | 2.5121 | 0.0144 | YES |
| 315d (15mo) | 60.51 | 1.35 | -14.72 | 62.1 | 2.5226 | 0.0141 | YES |
| 378d (18mo) | 53.99 | 1.26 | -15.16 | 63.5 | 2.6134 | 0.0112 | YES |

\* = current production configuration

**Alpha range:** 53.99% to 81.49% (spread: 27.50pp)
**Assessment:** All 5 lookback windows produce positive alpha. ROBUST to lookback choice.

### B. Rebalance Frequency Sensitivity

| Rebalance | Alpha (%) | Sharpe | Max DD (%) | Win Rate (%) | t-stat | p-value | Sig? |
|-|-|-|-|-|-|-|-|
| 10d | 85.86 | 1.59 | -14.53 | 56.6 | 2.7506 | 0.0067 | YES |
| 21d * | 81.49 | 1.6 | -14.45 | 62.3 | 2.5121 | 0.0144 | YES |
| 42d | 84.71 | 1.75 | -15.22 | 70.6 | 2.2736 | 0.0296 | YES |

**Alpha range:** 81.49% to 85.86% (spread: 4.37pp)
**Assessment:** All rebalance frequencies produce positive alpha. ROBUST to frequency choice.

### C. Summary Grid (3x3)

Cell format: Alpha (%) / Sharpe

| Lookback \ Rebalance | 10d (biweekly) | 21d (monthly) | 42d (bimonthly) |
|-|-|-|-|
| 189d (9mo) | 76.39 / 1.56 | 67.29 / 1.55 | 80.98 / 1.75 |
| 252d (12mo) | 85.86 / 1.59 | 81.49 / 1.6 ** | 84.71 / 1.75 |
| 315d (15mo) | 63.1 / 1.34 | 60.51 / 1.35 | 64.95 / 1.37 |

\*\* = current production configuration

**Grid cells with positive alpha:** 9/9
**Grid alpha range:** 60.51% to 85.86%
**Assessment:** Alpha is positive across ALL grid cells. Engine is ROBUST to parameter choice.

### D. Monte Carlo Weight Perturbation

- **Trials:** 100
- **Perturbation:** +/-20% uniform on each signal weight within each regime, renormalized
- **Baseline alpha:** 81.49%

| Metric | Value |
|-|-|
| Mean alpha | 81.48% |
| Std dev alpha | 0.66% |
| 5th percentile | 80.43% |
| 95th percentile | 82.62% |
| Min alpha | 79.83% |
| Max alpha | 82.9% |
| % trials with positive alpha | 100.0% |
| % trials within 2pp of base | 100.0% |
| Sign flips (vs baseline) | 0/100 |
| Mean Sharpe | 1.6 |
| Std Sharpe | 0.0 |

**VERDICT:** Alpha is **ROBUST** to weight perturbation. 100.0% of perturbations produce positive alpha.

## Overall Robustness Verdict

### US Engine: **ROBUST, Alpha persists across all parameter variations**

- Lookback sensitivity: [59.18%, 91.58%] (all positive)
- Rebalance sensitivity: [72.59%, 91.90%] (all positive)
- Grid: 9/9 cells positive alpha
- Monte Carlo: 100.0% positive, 0 sign flips in 100 trials
- MC alpha distribution: mean=81.64%, std=1.31%, 90% CI=[79.63%, 83.91%]

### India Engine: **ROBUST, Alpha persists across all parameter variations**

- Lookback sensitivity: [53.99%, 81.49%] (all positive)
- Rebalance sensitivity: [81.49%, 85.86%] (all positive)
- Grid: 9/9 cells positive alpha
- Monte Carlo: 100.0% positive, 0 sign flips in 100 trials
- MC alpha distribution: mean=81.48%, std=0.66%, 90% CI=[80.43%, 82.62%]

## Recommendations

1. If alpha is robust: proceed with current configuration. Consider slight parameter optimization toward best grid cell.
2. If alpha is fragile: reduce TILT_STRENGTH, consider equal-weighting signals, or switch to pure HRP (tilt=0).
3. If overfitting detected: do NOT deploy with signal tilts. Use HRP-only portfolio until more robust signals are found.
4. Regardless of result: continue expanding out-of-sample window. 11-month WF is minimum viable; 24+ months needed for confidence.

## Caveats on the Walk-Forward Design

- The training window is expanding (minimum 252 trading days), not rolling. HRP and signal statistics use all data up to the rebalance date, so the effective lookback grows from 252 days at the first step to the full history at the last.
- Steps are 21 trading days, not calendar months.
- Hyperparameters (tilt strength 0.5, weight bounds, regime thresholds, regime weight tables) were fixed before the walk-forward and are not re-optimized inside it. The walk-forward removes look-ahead in signal values, not in parameter choice.
- Any exception in a step falls back to equal weight for that step without a log entry, so a run can mix equal-weight and signal-driven periods.
- Period alpha is a raw return difference against the benchmark, not a beta-adjusted alpha.
- The universe is fixed to current constituents; see the survivorship bias study.
- Transaction costs in the engine walk-forward are a flat 10 bps (US) or 15 bps (India) of one-way turnover; the research scripts use a 5 bps spread plus a square-root impact model.
- The alpha figures in this file are cumulative percentage-point differences over the whole window, not annualized.
