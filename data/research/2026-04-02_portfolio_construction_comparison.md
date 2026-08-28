# Portfolio Construction Comparison: ERC vs Inverse Vol vs Equal Weight vs HRP

**Date:** 2026-04-02
**Status:** COMPREHENSIVE COMPARISON

## Hypothesis

DeMiguel et al. (2009) showed that 1/N (equal weight) often beats sophisticated optimization
in out-of-sample tests, especially with small stock universes. With only 9 US stocks, our
HRP-based portfolio construction may add complexity without adding value. This study tests
whether simpler approaches (inverse vol, equal weight) match or beat HRP and ERC in
walk-forward validation.

## Methodology

Four portfolio construction methods, each tested in identical walk-forward framework:
- **Equal Weight (1/N):** Simple 1/9 allocation to each stock
- **Inverse Volatility:** Weight proportional to 1/vol, using 63-day realized vol
- **Equal Risk Contribution (ERC):** Optimize so each stock contributes equally to portfolio risk
- **HRP (simplified):** Hierarchical Risk Parity with inverse-vol within clusters

All methods use:
- Monthly rebalancing (21-day steps)
- Weight bounds [2%, 40%]
- 10bps transaction costs
- NO signal tilts, pure portfolio construction comparison
- Benchmark: VOO

## Results

| Method | Sharpe | Ann. Return | Vol | Max DD | Ann. Turnover | Alpha t-stat | Alpha p-value |
|-|-|-|-|-|-|-|-|
| Equal Weight (1/N) | 1.2925 | 26.23% | 19.50% | -27.35% | 0.00x | 4.07 | 0.0001 |
| Inverse Volatility | 1.2361 | 21.71% | 17.08% | -25.99% | 0.50x | 2.86 | 0.0050 |
| Equal Risk Contribution | 1.2724 | 21.85% | 16.62% | -25.94% | 0.17x | 2.75 | 0.0069 |
| HRP (simplified) | 1.2426 | 21.92% | 17.14% | -26.06% | 0.14x | 2.94 | 0.0039 |

## Analysis

**Best:** Equal Weight (1/N) (Sharpe = 1.2925)
**Worst:** Inverse Volatility (Sharpe = 1.2361)
**Spread:** 0.0564

The spread between best and worst is **less than 0.10 Sharpe**, economically
insignificant and within estimation error. This confirms the DeMiguel et al. finding:
with 9 stocks, portfolio construction method does not matter much.

### Implication for our engine
HRP adds complexity (clustering, linkage, distance metric choices) without measurable
benefit over 1/N or inverse vol. However, HRP is already implemented and working.
The cost of switching is nonzero and the benefit is near zero.

**Recommendation:** Keep HRP. It is not worse than alternatives and provides a
theoretically sound framework that scales better if we expand the universe.

### For India (20 stocks)
The comparison is more relevant for the India engine with 20 stocks, where:
- Correlation structure is richer (IT exporters, banks, consumer clusters)
- HRP's clustering may add genuine value
- ERC optimization is better conditioned with 20 assets
- Ledoit-Wolf shrinkage (item 2.06) would help with 20/252 dimension ratio

**Recommendation for India:** Implement Ledoit-Wolf shrinkage as a low-risk improvement
to covariance estimation. One-line change using sklearn.covariance.LedoitWolf.

## Conclusion

**Verdict: REJECT (switching from HRP)**

No portfolio construction method significantly outperforms others with 9 US stocks.
Keep HRP. Consider Ledoit-Wolf shrinkage for the India engine as a hygiene improvement.
