# HMM Regime Detection Research

**Date:** 2026-04-01
**Status:** CONDITIONAL PASS, HMM shows statistical significance but pathological transition behavior makes it impractical without modifications

## Hypothesis

A 3-state Gaussian HMM trained on VIX + returns + macro features can outperform the heuristic VIX-threshold regime detection in quantshield/signals/regime.py, leading to better signal weight allocation and walk-forward alpha.

## Data

- **Universe:** 9 US equities + VOO benchmark + 6 macro indicators
- **Period:** 2016-04-04 to 2026-04-01 (2,471 trading days after feature construction)
- **Features:** VIX level, VIX 5-day change, 21-day benchmark return, 21-day benchmark vol, 21-day yield change, 21-day gold return

## Methodology

1. Full-sample 2-state and 3-state Gaussian HMM fit
2. Walk-forward: 3-year rolling training window, 3-month test periods
3. IC/ICIR analysis at 5d, 21d, 63d horizons
4. Quintile analysis on regime score
5. Regime-conditional forward return analysis
6. Transition matrix analysis
7. Cost analysis (regime transitions = forced rebalancing)
8. Bonferroni correction across the 15 signal families tested to date

## Results

### Full-Sample HMM Fit

**2-state model:**
| State | Label | Days | Mean VIX | Mean 21d Return |
|-|-|-|-|-|
| 0 | risk_on | 1,514 | 14.6 | +2.21% |
| 1 | crisis | 957 | 24.9 | -0.23% |

**3-state model:**
| State | Label | Days | Mean VIX | Mean 21d Return |
|-|-|-|-|-|
| 0 | risk_on | 750 | 14.6 | +2.24% |
| 1 | risk_off | 767 | 14.7 | +2.20% |
| 2 | crisis | 954 | 24.9 | -0.25% |

**CRITICAL FINDING:** The 3-state HMM collapsed states 0 and 1 into near-identical clusters (both ~14.6 VIX, both ~2.2% 21d return). The model effectively learned a 2-state solution with a degenerate third state. The risk_on/risk_off distinction is MEANINGLESS in this fit.

### Agreement with Heuristic

- HMM-3 vs Heuristic agreement: **36.3%** (barely above random for 3 classes)
- The heuristic classifies: risk_on=1,691, risk_off=639, crisis=141
- The HMM classifies: risk_on=750, risk_off=767, crisis=954
- HMM is far more willing to call "crisis" (954 days vs 141 days). This aggressive crisis classification drives the IC difference.

### IC Analysis (Regime Score: risk_on=+1, risk_off=0, crisis=-1)

| Horizon | HMM IC | HMM ICIR | Heuristic IC | Heuristic ICIR |
|-|-|-|-|-|
| 5-day | -0.0327 | -0.2659 | -0.1134 | -1.2456 |
| 21-day | -0.0999 | -0.5709 | -0.1931 | -1.5127 |
| 63-day | -0.1624 | -0.5835 | -0.2195 | -1.6650 |

**Interpretation:** Both signals show NEGATIVE IC, meaning higher regime score (risk_on) is associated with LOWER forward returns. This is expected: the market pays a premium for bearing crisis risk. The heuristic actually shows STRONGER ICs and ICIRs than HMM across all horizons. The heuristic's tighter crisis definition (only 141 days) creates a more informative signal.

**Bonferroni:** HMM regime score p-value=0.000001, passes Bonferroni (alpha=0.0033). Statistically significant.

### Regime-Conditional Forward Returns (21-day)

| Regime | HMM Mean | HMM Count | Heuristic Mean | Heuristic Count |
|-|-|-|-|-|
| risk_on | +1.01% | 750 | +0.87% | 1,691 |
| risk_off | +1.00% | 767 | +1.27% | 639 |
| crisis | +1.63% | 954 | +5.74% | 141 |

**Key finding:** The heuristic's crisis detection identifies a much richer opportunity set (+5.74% mean 21d forward return after crisis classification vs +1.63% for HMM). The heuristic is more selective and more profitable per crisis signal.

### Walk-Forward Performance

| Metric | HMM | Heuristic | Benchmark |
|-|-|-|-|
| Cumulative Return | 179.03% | 177.13% | 102.32% |
| Avg Agreement | 48.1% | n/a | n/a |

HMM edges out heuristic by 1.9% cumulative, but this is within noise given the 48% agreement rate.

### Transition Matrix (3-state)

```
         risk_on  risk_off  crisis
risk_on  [0.001,  0.999,    0.000]
risk_off [0.970,  0.005,    0.026]
crisis   [0.004,  0.015,    0.981]
```

**PATHOLOGICAL BEHAVIOR:** The risk_on state has 99.9% probability of transitioning to risk_off on the next day, and risk_off has 97% probability of transitioning back to risk_on. This creates alternating-day regime flipping between risk_on and risk_off. Only the crisis state is persistent (98.1% self-transition).

### Regime Persistence

| Regime | Avg Run Length | Number of Runs |
|-|-|-|
| risk_on | 1.0 days | 750 |
| risk_off | 1.0 days | 767 |
| crisis | 50.2 days | 19 |

This confirms the pathology: risk_on and risk_off alternate daily. Only crisis is a real persistent state.

### Cost Analysis

| Metric | HMM | Heuristic |
|-|-|-|
| Transitions/year | 156.5 | 22.8 |
| Est. annual cost | 2.35% | 0.34% |

HMM generates 7x more transitions, costing ~2% more annually in friction. This alone would erase any marginal alpha.

## Verdict: CONDITIONAL PASS

### What works:
1. The HMM's CRISIS state is genuinely persistent and well-identified (avg 50-day runs, mean VIX=24.9)
2. The 2-state model cleanly separates risk-on from elevated-risk periods
3. Passes Bonferroni significance test

### What fails:
1. 3-state model degenerates, risk_on and risk_off are indistinguishable
2. Daily regime flipping between non-crisis states creates 7x transition cost
3. Heuristic has stronger IC/ICIR across all horizons
4. Heuristic identifies a more profitable crisis regime (+5.74% vs +1.63%)

### Recommendation for Engineering:
**Use a 2-state HMM as a SUPPLEMENTARY crisis detector, NOT a replacement for the heuristic.** Specifically:
1. Train 2-state HMM on VIX + returns + macro features
2. When HMM says "crisis" AND heuristic says "risk_off" or "crisis", increase crisis confidence
3. When HMM says "risk_on" but heuristic says "crisis", reduce crisis confidence
4. Do NOT use HMM for the risk_on/risk_off distinction, the heuristic VIX thresholds are superior
5. Retrain monthly, not daily, to reduce transition noise
6. Add regime persistence filter: require 5+ consecutive days in new regime before switching

This hybrid approach captures HMM's multi-feature crisis detection without the pathological transition behavior.

### Implementation Priority: MEDIUM

The marginal improvement over the heuristic is small (1.9% cumulative over ~7 years walk-forward). The engineering complexity of maintaining an HMM model that needs retraining is significant. Only implement if the hybrid approach can be tested to show >50bps/year improvement after costs.

## Appendix: Bonferroni Status

Fourteen signal families had been tested at this point. Bonferroni alpha = 0.0033.
HMM regime score: p=0.000001. **PASSES.**
