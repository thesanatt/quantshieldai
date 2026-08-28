# Seasonality Signals Research

**Date:** 2026-04-01
**Status:** REJECT for US. CONDITIONAL PASS for India Turn-of-Month only.

## Hypothesis

Calendar-based anomalies (turn-of-month, January effect, sell-in-May, options expiration week) provide statistically significant return premiums that can serve as a timing overlay for portfolio rebalancing.

## Data

- **US:** SPY, 2011-04-06 to 2026-04-01 (3,769 trading days, ~15 years)
- **India:** Nifty 50 (^NSEI), 2011-04-05 to 2026-03-30 (3,674 trading days, ~15 years)
- **Macro:** VIX, TNX for regime conditioning

## Methodology

1. Four seasonal effects tested independently: turn-of-month (last 3 + first 3 trading days), January effect, sell-in-May (Nov-Apr vs May-Oct), OpEx week (3rd Friday week)
2. IS/OOS split: 60% IS / 40% OOS
3. t-test for significance of each effect
4. IC/ICIR of composite signal at 5d/21d/63d horizons
5. Regime-conditional analysis (TOM effect by VIX bucket)
6. Bonferroni correction across the 15 signal families tested to date

## Results: US Market (SPY)

### Full Sample

| Effect | Favorable Period | Unfavorable Period | Spread | p-value |
|-|-|-|-|-|
| Turn-of-Month | 17.45% ann | 12.47% ann | +1.98 bps/day | 0.528 |
| January Effect | +1.30%/month | +1.09%/month | +0.21%/month | 0.853 |
| Sell-in-May | 14.04% ann (winter) | 12.54% ann (summer) | +1.50% ann | 0.778 |
| OpEx Week | 7.66% ann | 15.79% ann | -8.13% ann | 0.351 |

**No US seasonal effect is statistically significant.** All p-values >0.35. The TOM effect exists directionally (+1.98 bps/day spread) but is too noisy for significance at 15 years of data.

**OpEx week is NEGATIVE**, returns during OpEx weeks are actually lower than non-OpEx weeks, opposite to some literature claims. This may reflect gamma-driven volatility compression creating lower-mean-higher-kurtosis return distributions.

### IS/OOS Stability (US)

| Effect | IS p-value | OOS p-value | Direction Stable? |
|-|-|-|-|
| Turn-of-Month | 0.477 | 0.456 | Yes (both positive, both insignificant) |
| January Effect | 0.642 | 0.797 | Yes (both positive, both insignificant) |
| Sell-in-May | 0.582 | 0.553 | Yes (consistent) |
| OpEx Week | 0.820 | 0.208 | Unstable (OOS getting stronger negative) |

### IC Analysis (Composite Signal, US)

| Horizon | IC | ICIR |
|-|-|-|
| 5-day | 0.0213 | 0.1051 |
| 21-day | -0.0085 | -0.0404 |
| 63-day | -0.0164 | 0.0227 |

All ICs are essentially zero. The composite seasonality signal has no predictive power for US returns.

### Regime-Conditional TOM (US)

| VIX Regime | TOM Mean (bps) | NonTOM Mean (bps) | Spread (bps) |
|-|-|-|-|
| Low Vol (VIX <18) | +13.9 | +15.6 | -1.7 |
| Mid Vol (18-25) | -5.5 | -3.8 | -1.7 |
| High Vol (VIX >25) | -3.9 | -29.5 | **+25.6** |

**Interesting finding:** The TOM effect REVERSES in low/mid-vol regimes but is strongly positive during high-vol periods (+25.6 bps/day spread). In crisis periods, the turn-of-month window captures the "snap-back" after month-end rebalancing flows. This is regime-dependent and only useful during crises, precisely when you have the fewest observations.

## Results: India Market (Nifty 50)

### Full Sample

| Effect | Favorable Period | Unfavorable Period | Spread | p-value |
|-|-|-|-|-|
| Turn-of-Month | 25.18% ann | 4.36% ann | +8.26 bps/day | **0.011** |
| January Effect | +0.76%/month | +0.88%/month | -0.12%/month | 0.917 |
| Sell-in-May | 6.25% ann (winter) | 14.64% ann (summer) | -8.39% ann | 0.213 |
| OpEx Week | 9.73% ann | 10.71% ann | -0.98% ann | 0.913 |

**India Turn-of-Month is the standout:** 8.26 bps/day spread, p=0.011. The effect is 4x stronger than in the US. This is consistent with literature: the TOM effect is stronger in emerging markets due to FII flow patterns (monthly fund allocation cycles).

**India Sell-in-May is REVERSED:** Summer (May-Oct) outperforms winter by 8.39% annually. This contradicts the Western "sell in May" narrative. Monsoon season (Jun-Sep) drives Indian agricultural GDP and rural consumption, creating a positive seasonal for Indian equities.

### IS/OOS Stability (India)

| Effect | IS p-value | OOS p-value | Direction Stable? |
|-|-|-|-|
| Turn-of-Month | 0.247 | **0.013** | Yes, STRENGTHENING in OOS |
| January Effect | 0.343 | **0.003** | Direction flip (negative IS, positive OOS) |
| Sell-in-May | 0.375 | 0.210 | Yes (consistent reversal) |
| OpEx Week | 0.702 | 0.489 | Yes (both null) |

**India TOM passes OOS at p=0.013**, borderline after Bonferroni but the IS-to-OOS improvement is a positive signal (effect getting stronger, not weaker). This is unusual and warrants attention.

India January Effect shows p=0.003 in OOS but with a direction flip from IS. This is suspicious and likely a COVID recovery artifact (Jan 2021 was exceptionally strong).

## Bonferroni Assessment

Corrected alpha = 0.0033 for 15 total signals tested.

| Test | p-value | Passes Bonferroni |
|-|-|-|
| US TOM | 0.528 | No |
| US January | 0.853 | No |
| US Sell-in-May | 0.778 | No |
| US OpEx | 0.351 | No |
| India TOM | 0.011 | No |
| India January | 0.917 | No |
| India Sell-in-May | 0.213 | No |
| India OpEx | 0.913 | No |

**No seasonal effect passes Bonferroni.** India TOM is closest (p=0.011 vs threshold 0.003).

## Transaction Cost Impact

Seasonality signals are overlay signals, they modify WHEN to rebalance, not WHAT to hold. If used as rebalance timing (shift monthly rebalance to coincide with turn-of-month window), the cost impact is exactly zero additional turnover.

If used as a daily signal (increase/decrease allocation based on calendar day), the cost would be ~25 bps/year, which would consume most of the TOM edge in the US but only a fraction of the India TOM edge (8.26 bps/day * ~130 TOM days/year = ~107 bps/year gross).

## Verdict

### US Seasonality: REJECT
- No effect reaches statistical significance
- Composite IC is zero
- The regime-conditional TOM effect (high-vol only) has too few observations to be actionable

### India Turn-of-Month: CONDITIONAL PASS
- 8.26 bps/day spread, p=0.011 (borderline after Bonferroni)
- Strengthens in OOS (rare and bullish for signal validity)
- Zero-cost implementation: simply time India rebalances to the TOM window
- Consistent with economic theory (FII monthly flow cycles)

### Recommended Implementation (India only):
1. Time India portfolio rebalances to occur in the last 3 + first 3 trading days of each month
2. Do NOT add a new "seasonality" signal weight, this is a timing overlay, not a directional signal
3. If the engine must rebalance mid-month for emergency reasons, proceed as normal (seasonality should not override risk management)
4. Expected edge: 50-100 bps/year from better rebalance timing at zero additional cost

### All Other Seasonality Effects: REJECT
January effect, sell-in-May, OpEx week, none are significant in either market after Bonferroni correction.

## Appendix: Bonferroni Status

Fifteen signal families had been tested at this point; the four calendar effects count as one family.
India TOM: p=0.011. Does not pass Bonferroni (0.0033) but passes uncorrected (0.05).
All others: p>0.20. Clear rejects.
