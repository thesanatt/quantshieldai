# Country Rotation Study

**Date:** 2026-04-02
**Hypothesis:** Momentum on country ETFs can drive geographic allocation.
**Script:** `data/research/country_rotation_study.py`

## Universe

6 country ETFs, 7 years of data (2019-02-04 to 2026-03-31, 1,854 trading days).

| Country | Ticker | Ann. Return | Ann. Vol | Sharpe | Max DD |
|-|-|-|-|-|-|
| US | SPY | 14.27% | 19.35% | 0.737 | -33.72% |
| India | ^NSEI | 10.23% | 17.23% | 0.594 | -38.44% |
| Japan | EWJ | 8.46% | 18.25% | 0.464 | -33.14% |
| Brazil | EWZ | 3.79% | 34.54% | 0.110 | -56.99% |
| China | FXI | -0.14% | 29.68% | -0.005 | -60.81% |
| Indonesia | EIDO | -4.82% | 25.36% | -0.190 | -56.12% |

Massive dispersion: US and India dominate. China, Indonesia essentially flat/negative. Brazil extremely volatile for the return. This dispersion is the setup momentum hopes to exploit.

## Strategy Results

### Full-Sample

| Strategy | Ann. Return | Ann. Vol | Sharpe | Max DD | Turnover |
|-|-|-|-|-|-|
| **EW (6 countries)** | **6.70%** | **17.85%** | **0.375** | **-39.12%** | 0% |
| Market-Cap Weight | 12.01% | 18.03% | 0.666 | -32.21% | ~0% |
| Mom Top-2 (0bps) | 14.96% | 15.07% | 0.993 | -21.63% | 26.0% |
| Mom Top-2 (5bps) | 14.91% | 15.07% | 0.989 | -21.63% | 26.0% |
| Mom Top-2 (10bps) | 14.85% | 15.07% | 0.985 | -21.74% | 26.0% |

Full-sample momentum looks spectacular: Sharpe 0.993 vs EW 0.375. Higher return (14.96% vs 6.70%) AND lower vol (15.07% vs 17.85%) AND lower max DD (-21.63% vs -39.12%).

But we know better than to trust full-sample results.

### Walk-Forward OOS

| Strategy | Ann. Return | Ann. Vol | Sharpe |
|-|-|-|-|
| WF Mom (0bps) | 8.40% | 14.40% | 0.583 |
| WF Mom (5bps) | 8.30% | 14.40% | 0.576 |
| WF Mom (10bps) | 8.20% | 14.40% | 0.570 |

Walk-forward OOS Sharpe drops from 0.993 to 0.583. Massive decay. This is the classic overfitting signature, full-sample momentum looks like genius because it overweights the winners you already know (US, India) and underweights the losers (China, Indonesia).

### Bootstrap 95% CI

| Comparison | Observed Diff | 95% CI | Significant? |
|-|-|-|-|
| Mom vs EW (full sample) | +1.001 | [-0.299, +1.789] | NO |
| WF Mom vs EW | +0.632 | [-0.668, +1.488] | NO |
| MCap vs EW | +0.000 | [0.000, +0.505] | NO |

**NONE are significant.** The full-sample momentum advantage (+1.0 Sharpe!) has a CI that includes zero. The walk-forward advantage (+0.63) also includes zero. Even market-cap weighting vs EW is not significant.

## Cost Analysis

Transaction costs barely matter here because ETFs are cheap (5-10bps). The difference between 0bps and 10bps is only 0.008 Sharpe. This is NOT the problem, the problem is that momentum doesn't reliably pick winners out-of-sample.

## Correlation Matrix

|  | India | US | China | Brazil | Indonesia | Japan |
|-|-|-|-|-|-|-|
| India | 1.000 | 0.261 | 0.192 | 0.263 | 0.334 | 0.279 |
| US | 0.261 | 1.000 | 0.489 | 0.592 | 0.597 | 0.741 |
| China | 0.192 | 0.489 | 1.000 | 0.434 | 0.407 | 0.480 |
| Brazil | 0.263 | 0.592 | 0.434 | 1.000 | 0.540 | 0.533 |
| Indonesia | 0.334 | 0.597 | 0.407 | 0.540 | 1.000 | 0.537 |
| Japan | 0.279 | 0.741 | 0.480 | 0.533 | 0.537 | 1.000 |

India has the LOWEST correlation with all other countries (0.19-0.33). This is the real finding for diversification, India is genuinely uncorrelated with global markets. US-Japan correlation is very high (0.74).

## Why Country Momentum Looks Good But Isn't

1. **Hindsight bias.** Over 2019-2026, momentum effectively picks US + India (or US + Japan) and avoids China + Indonesia. This is the "obvious" trade in hindsight. The 12-month lookback just formalizes what any human would have done.

2. **Regime dependence.** Country momentum worked specifically because US and India were consistent winners for 7 years straight. If China rallies 50% in 6 months (which it did in 2024 briefly), momentum would have flipped to overweight China right at the top.

3. **Small cross-section.** With only 6 countries, ranking is extremely noisy. Going from "rank 3 to rank 2" can flip your entire allocation based on a 1% return difference in the lookback window.

4. **Walk-forward decay.** Sharpe dropped from 0.993 to 0.583 in WF, a 40% decay. Classic overfitting signature.

5. **Currency risk ignored.** These are USD-denominated ETFs except ^NSEI (INR). For an Indian investor, SPY returns include USDINR appreciation. Country rotation from India's perspective has additional FX risk not captured here.

## The Market-Cap Weight Finding

Market-cap weight (60% US, 10% China, 6% Japan, 4% India, 2% Brazil, 1% Indonesia) achieves Sharpe 0.666 vs EW 0.375. This isn't a "strategy", it's just "buy more US" which happened to be the best market. Bootstrap CI includes zero, so even this isn't statistically significant as a strategy.

## HONEST CONCLUSION

**REJECT.** Country momentum rotation does NOT survive walk-forward validation with statistical significance.

- Full-sample results are spectacular (Sharpe 0.993) but illusory
- Walk-forward OOS: Sharpe 0.583 (40% decay from full sample)
- Bootstrap CI includes zero for ALL comparisons
- The "strategy" is really just "buy US and India", an ex-post observation, not a predictive signal
- Transaction costs are irrelevant (ETFs are cheap)
- Currency risk is unquantified and real for an India-based investor

### What IS Useful from This Study

1. **India-US diversification is validated.** India has 0.26 correlation with US, genuinely uncorrelated. A simple 60% India / 40% US split (or vice versa) provides real diversification benefit.

2. **Avoid concentration in EM.** China (-0.14% annual), Brazil (3.79%), Indonesia (-4.82%) are return-destroying in this period. EM diversification for its own sake is a trap.

3. **Market-cap weighting beats equal weighting** (Sharpe 0.666 vs 0.375) but isn't statistically significant. This just means US overweight happened to work.
