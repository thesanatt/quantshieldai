# Multi-Asset Regime Timing Study

**Date:** 2026-04-02
**Hypothesis:** Use the engine's regime detector to time allocation between equity, gold, and liquid funds.
**Script:** `data/research/multi_asset_regime_timing.py`

## Data Availability

All tickers available with good coverage:
- NIFTYBEES.NS: 1,275 days
- GOLDBEES.NS: 1,275 days
- India VIX: 1,261 days
- Nifty 50: 1,275 days
- USDINR: 1,342 days
- Crude Oil: 1,299 days

Period: ~5 years (2021-02 to 2026-03). 1,093 days in backtest (after 252-day warmup).

## Allocation Rules

| Regime | Equity (NIFTYBEES) | Gold (GOLDBEES) | Liquid (6% annual) |
|-|-|-|-|
| Risk-On | 100% | 0% | 0% |
| Risk-Off | 60% | 30% | 10% |
| Crisis | 30% | 50% | 20% |

## Regime Distribution

| Regime | Simple (VIX only) | Full (VIX + Nifty + INR + Oil) |
|-|-|-|
| Risk-On | 864 days (79%) | 775 days (71%) |
| Risk-Off | 208 days (19%) | 263 days (24%) |
| Crisis | 22 days (2%) | 56 days (5%) |

The simplified VIX-only detector is overwhelmingly risk-on (79% of days). Crisis is extremely rare (22 days total over 5 years). The full detector is slightly more conservative (71% risk-on, 5% crisis).

## Regime Change Frequency, CRITICAL

| Detector | Total Changes | Avg Days per Regime |
|-|-|-|
| Simple (VIX only) | 47 | 23.3 days |
| Full (multi-factor) | 115 | 9.5 days |

**The full detector flips regime every 9.5 days on average.** This is WAY too frequent for a strategy that reallocates across asset classes. At 10-20bps per rebalance, that's 4-8% annual cost from regime switching alone.

The simple detector is better at 23.3 days average, but still 47 regime changes over ~4.3 years = ~11 per year.

## Performance Results

### Simple Regime Timing (VIX only)

| Strategy | Ann. Return | Ann. Vol | Sharpe | Max DD |
|-|-|-|-|-|
| **Buy & Hold NIFTY** | **6.33%** | **12.26%** | **0.517** | **-15.23%** |
| Regime Timing (Simple) | 6.25% | 10.65% | 0.587 | -16.27% |

Sharpe improvement: +0.070 (0.517 to 0.587).
Bootstrap 95% CI: [-0.312, +0.450], NOT SIGNIFICANT.

The timing strategy reduces vol by 1.6pp (12.26% to 10.65%) but also reduces return by 0.08pp. The Sharpe improvement is entirely from lower vol, not higher return. And max DD is actually WORSE (-16.27% vs -15.23%).

### Full Regime Timing (VIX + Nifty + INR + Oil)

| Strategy | Ann. Return | Ann. Vol | Sharpe | Max DD |
|-|-|-|-|-|
| **Buy & Hold NIFTY** | **6.33%** | **12.26%** | **0.517** | **-15.23%** |
| Regime Timing (Full) | 4.60% | 10.58% | 0.435 | -20.40% |

**The full detector DESTROYS value.** Return drops from 6.33% to 4.60%, vol from 12.26% to 10.58%, but the return hit is far larger than the vol reduction. Sharpe drops from 0.517 to 0.435. Max DD is WORSE at -20.40%.

Bootstrap 95% CI: [-0.540, +0.392], NOT SIGNIFICANT (and negative direction).

## Crisis Hit Rate Analysis

When the model says "crisis," what actually happens next?

| Detector | Crisis Days | Mean 5d Fwd Return | % Negative 5d | Median 5d Fwd |
|-|-|-|-|-|
| Simple | 22 | +1.157% | 31.6% | +2.148% |
| Full | 56 | +0.656% | 37.3% | +0.803% |

**The crisis detector is a CONTRARIAN indicator.** When it says "crisis," the next 5 days are POSITIVE on average (+1.16% for simple, +0.66% for full). This means going defensive during "crisis" COSTS you because you're de-risking right when the market is about to bounce.

Only 31.6% (simple) and 37.3% (full) of crisis signals are followed by negative 5-day returns. A random coin flip would be 50%.

## Why Regime Timing Fails Here

1. **VIX is mean-reverting.** High VIX (which triggers risk-off/crisis) typically coincides with the bottom, not the start of a decline. Going defensive after VIX spikes means you miss the recovery.

2. **Regime detection is backward-looking.** By the time VIX > 25, the crash has already happened. You're selling low and buying high when VIX reverts.

3. **Risk-on dominance.** With 79% of days in risk-on (full equity), the timing strategy IS mostly buy-and-hold. The remaining 21% of days is when you go to 60/30/10 or 30/50/20, which just drags returns during what are often recovery periods.

4. **The full detector is WORSE because it's noisier.** 115 regime changes (every 9.5 days) means constant whipsawing. Each false crisis signal costs you exposure to equity upside.

5. **No lookahead bias.** We used previous day's regime to determine today's allocation, which is correct. But the regime detector is still reactive, it flags regimes AFTER they've already been priced in.

## HONEST CONCLUSION

**REJECT.** Regime timing using the engine's regime detector does NOT generate alpha for asset allocation.

- Simple detector: +0.07 Sharpe improvement, CI [-0.31, +0.45], NOT significant
- Full detector: -0.08 Sharpe (WORSE), CI [-0.54, +0.39], NOT significant
- Crisis signals are contrarian: positive mean forward returns when model says "crisis"
- Full detector flips every 9.5 days, way too noisy for implementation
- Max drawdown is WORSE for timing vs buy-and-hold

The regime detector has value as a RISK MONITORING tool (alerting users to elevated risk) but NOT as an ALLOCATION TIMING tool. This is consistent with our existing finding: the engine's value is in risk awareness, not in trading signals.
