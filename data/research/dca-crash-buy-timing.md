# Contribution Timing During Volatility Spikes

**Date:** 2026-04-01
**Question:** Does doubling a fixed monthly contribution when implied volatility spikes add value beyond the extra capital deployed?

## Setup

- SPY: 5,000 USD per month, 400 months (January 1993 to April 2026)
- Nifty 50: 1,00,000 INR per month, 218 months (September 2007 to April 2026)
- Strategy A (steady): fixed monthly contribution
- Strategy B (crash-buy): 2x contribution in months when VIX > 30 (US) or India VIX > 25 (India)
- Strategy C (fair comparison): the same total capital as B, spread evenly across all months

Strategy C separates the timing effect from the effect of investing more money.

## Trigger Frequency

| Market | High-VIX months | Total months | Frequency |
|-|-|-|-|
| US (VIX > 30) | 32 | 400 | 8.0% |
| India (India VIX > 25) | 40 | 218 | 18.3% |

## SPY (values in USD)

| Horizon | Steady | Crash-buy | Crash-buy vs steady | Fair comparison | Crash-buy vs fair |
|-|-|-|-|-|-|
| 10 yr | 760,869 | 804,144 | +5.7% | 821,738 | -2.1% |
| 20 yr | 2,305,499 | 2,505,166 | +8.7% | 2,489,939 | +0.6% |
| 30 yr | 8,474,797 | 9,174,111 | +8.3% | 9,152,781 | +0.2% |

Against the fair comparison the timing effect is +0.2% over 30 years and negative at 10 years. Crisis windows (GFC 2008, COVID 2020, 2022 rate hikes) each show about +8% one and three years later, which matches the extra capital deployed rather than any timing effect.

## Nifty 50 (values in INR)

| Horizon | Steady | Crash-buy | Crash-buy vs steady | Fair comparison | Crash-buy vs fair |
|-|-|-|-|-|-|
| 10 yr | 2.14 Cr | 2.91 Cr | +36.2% | 2.53 Cr | +15.1% |
| 15 yr | 4.32 Cr | 5.71 Cr | +32.0% | 5.12 Cr | +11.5% |
| 18.2 yr (full sample) | 6.05 Cr | 7.88 Cr | +30.3% | 7.16 Cr | +10.1% |

Crisis windows: GFC 2008 (7 high-VIX months, 6,00,000 INR extra) +90.6% one year later and +62.3% three years later; COVID 2020 (3 months, 2,00,000 INR extra) +33.4% and +31.8%.

## Verdict

- US: no timing value. The apparent advantage is extra capital.
- India: a positive timing effect of +10 to +15% over 10 to 18 years after controlling for capital, driven by two episodes (2008 and 2020). Two episodes are not enough to treat this as a validated rule.
- Status: rejected as a signal and not implemented. The engine holds no cash reserve and does not schedule contributions.
