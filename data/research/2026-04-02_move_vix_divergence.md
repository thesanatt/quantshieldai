# MOVE/VIX Divergence as Regime Signal

**Date:** 2026-04-02
**Signal:** Bond vol (MOVE) vs Equity vol (VIX) divergence

## Signal Description and Hypothesis

The MOVE index (Merrill Lynch Option Volatility Estimate) measures Treasury bond implied
volatility. VIX measures equity implied volatility. These normally co-move. When they
diverge (MOVE spikes but VIX stays calm, or vice versa), it signals a dislocation between
bond and equity risk pricing.

**Hypothesis:** MOVE/VIX ratio z-score > 2 (bond stress without equity fear) precedes equity
corrections within 2-4 weeks. MOVE/VIX z-score < -2 (equity fear without bond stress)
signals faster VIX mean-reversion and is contrarian bullish.

## Data and Methodology

- MOVE index data: 2827 trading days
- VIX data: aligned to MOVE dates
- MOVE/VIX ratio computed daily, z-scored over 63-day rolling window
- Forward returns: 5-day and 21-day VOO returns
- Regime buckets: >90th percentile (high), <10th percentile (low), normal

## Results

### Information Coefficient

| Horizon | IC | p-value | Significant? |
|-|-|-|-|
| 5-day | -0.0171 | 0.3703 | NO |
| 21-day | 0.0071 | 0.7114 | NO |

### Conditional Forward Returns (21-day)

| MOVE/VIX Regime | Avg 21d Return | Std | n |
|-|-|-|-|
| High MOVE/VIX (>90pct) | 1.4448% | 3.6049% | 277 |
| Low MOVE/VIX (<10pct) | 1.7579% | 5.8397% | 276 |
| Normal MOVE/VIX | 1.0488% | 4.3601% | 2191 |

## Conclusion

**Verdict: REJECT**

The MOVE/VIX divergence does not show meaningful predictive power for forward returns.
Information coefficients are near zero at both 5-day and 21-day horizons.
The conditional return analysis does not show economically significant differences
between high/low MOVE/VIX regimes.
