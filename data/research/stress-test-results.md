# Comprehensive Stress Test Results

**Date:** 2026-04-01
**Engines tested:** v2.0 (US) and India engine
**Methodology:** Walk-forward simulation with 21-day rebalancing, 10bps transaction costs, regime weight tables from config.py

## Crisis 1: COVID-19 Crash (Jan-Jun 2020)

### Market Context
- VIX went from 12.5 (Jan 2) to 82.7 (Mar 16), the highest VIX reading ever recorded
- SPY peak (Feb 19) to trough (Mar 23): -33.9%
- Fastest bear market in history: 22 trading days from peak to -30%
- Fed emergency rate cut Mar 3, QE infinity Mar 23

### Engine Regime Detection Timeline

| Date | Regime | Confidence | VIX | Key Details |
|-|-|-|-|-|
| 2020-01-02 | risk_on | 0.57 | 12.5 | Normal conditions |
| 2020-02-03 | risk_on | 0.80 | 18.0 | Still risk_on despite VIX rising |
| 2020-03-04 | **CRISIS** | 0.62 | 32.0 | First crisis detection |
| 2020-04-02 | **CRISIS** | 0.67 | 50.9 | Deep crisis, VIX still extreme |
| 2020-05-04 | **CRISIS** | 0.71 | 36.0 | Crisis persisting |
| 2020-06-03 | risk_off | 0.38 | 25.7 | De-escalation beginning |

**Analysis:**
- Engine correctly detected crisis by Mar 4, after VIX crossed 30. This is ~9 trading days after the peak (Feb 19) and ~14 trading days before the trough (Mar 23).
- Engine MISSED the initial Feb 19-Mar 3 crash (VIX 14->28, SPY -13%). The heuristic only triggers crisis at VIX 30+.
- Engine correctly maintained crisis through the recovery period (Apr-May), avoiding premature risk-on signals.
- De-escalated to risk_off on Jun 3, appropriate timing as VIX was still elevated but declining.

**Regime detection gap:** The Feb 19 to Mar 4 window represents a ~$13,000 loss on a $100k portfolio that the engine did not defensively position for. An HMM-based detector might have flagged this 5-7 days earlier based on the multi-feature deterioration.

### Emergency Triggers

| Date | Triggers Fired |
|-|-|
| 2020-03-04 | Regime = CRISIS |
| 2020-04-02 | Regime = CRISIS |
| 2020-05-04 | Regime = CRISIS |

**VIX trigger (>40) did NOT fire on the rebalance dates** because the rebalance fell on dates when VIX was at 32, 50.9, and 36, only the Apr 2 date was >40. However, VIX was >40 from Mar 9 to Apr 7. The monthly rebalance cycle means the engine only evaluates triggers at 21-day intervals, so the VIX=82 peak on Mar 16 was between rebalance dates.

**Emergency flag:** the crisis trigger fired on Mar 4, Apr 2, and May 4. The engine held 100% equity throughout (no cash or bond sleeve), so the flag could only inform external contributions.

### Walk-Forward Portfolio Performance

| Metric | Engine Portfolio | VOO Benchmark |
|-|-|-|
| Total Return (Jan-Jun 2020) | **+12.78%** | -4.08% |
| Max Drawdown | **-25.89%** | -33.99% |
| Sharpe Ratio | **0.79** | n/a |

### Portfolio Weights During Crisis

The crisis regime shifted signal weights to:
- Mean reversion: 0.30 (from 0.05 in risk_on), the primary driver of outperformance
- Cross-asset: 0.20 (from 0.10)
- Momentum: 0.15 (from 0.35), correctly reduced momentum in a trend-reversal environment
- HRP base weights favored low-vol names (JNJ, KO) during the crash period, providing some defensive tilt

## Crisis 2: 2022 Rate Hike Selloff (Jan-Dec 2022)

### Market Context
- Fed funds rate: 0-0.25% to 4.25-4.50%
- SPY: -18.67% for 2022
- 10Y yield: 1.52% to 3.87%
- Both stocks AND bonds fell, traditional diversification failed
- Gradual grind lower, not a sharp crash

### Engine Regime Detection Timeline

| Date | Regime | Confidence | VIX | Key Details |
|-|-|-|-|-|
| 2022-01-03 | risk_on | 0.57 | 16.6 | Start of year |
| 2022-02-02 | risk_on | 0.33 | 22.1 | Low confidence risk_on |
| 2022-03-04 | **CRISIS** | 0.88 | 32.0 | Russia-Ukraine spike |
| 2022-04-04 | risk_on | 0.71 | 18.6 | False all-clear |
| 2022-05-04 | risk_off | 0.62 | 25.4 | Re-escalation |
| 2022-06-03 | risk_on | 0.33 | 24.8 | Low confidence flip |
| 2022-07-06 | risk_on | 0.50 | 26.7 | Misclassification |
| 2022-08-04 | risk_on | 0.50 | 21.4 | Summer bear rally |
| 2022-09-02 | risk_off | 0.71 | 25.5 | Jackson Hole aftermath |
| 2022-10-04 | risk_off | 0.67 | 29.1 | Near trough |
| 2022-11-02 | risk_off | 0.50 | 25.9 | Inflation pivot hopes |
| 2022-12-02 | risk_on | 0.67 | 19.1 | Year-end rally |

**Analysis:**
- The engine STRUGGLED with 2022. The gradual selloff never produced sustained VIX >35, so crisis detection was brief (only March, when Russia-Ukraine caused a spike).
- **Regime whipsaw:** 6 regime changes in 12 months, alternating between risk_on and risk_off. This generated excessive turnover with inconsistent positioning.
- Low confidence readings (0.33, 0.50) appeared frequently, the engine was uncertain throughout.
- The false risk_on signals in Jun-Aug (VIX 21-27) were particularly damaging: the engine ran momentum-heavy weights during a downtrend.

**This is the engine's worst-case scenario:** a slow, grinding bear market with moderate (not extreme) VIX. The heuristic's binary VIX thresholds cannot distinguish "moderately elevated VIX in a bear market" from "moderately elevated VIX in a normal pullback."

### Emergency Triggers

| Date | Triggers Fired |
|-|-|
| 2022-03-04 | Regime = CRISIS |

Only one emergency trigger in all of 2022. VIX never sustained >40 on a rebalance date. No individual stock dropped >5% on a rebalance date. The crash-buy protocol was virtually inactive during a -25% drawdown.

**This is a design flaw:** the emergency triggers are calibrated for acute crashes (COVID, flash crash), not secular bear markets. The 2022 drawdown never produced a signal.

### Walk-Forward Portfolio Performance

| Metric | Engine Portfolio | VOO Benchmark |
|-|-|-|
| Total Return (2022) | **-13.36%** | -18.67% |
| Max Drawdown | **-22.35%** | -24.52% |
| Sharpe Ratio | **-0.55** | n/a |

## Crisis 3: India COVID Crash (Jan-Jun 2020)

### Market Context
- Nifty 50 peak (Jan 20): ~12,430
- Nifty 50 trough (Mar 23): ~7,511 (-39.6%)
- India VIX spiked to 86 (higher than US VIX)
- India lockdown announced Mar 24 (most stringent in the world)
- FII outflows exceeded INR 60,000 Cr in March 2020

### Engine Regime Detection

Engine used the same VIX-based heuristic (using ^VIX, not India VIX, since India macro tickers in current config include ^INDIAVIX but the US engine was applied here).

### Walk-Forward Portfolio Performance

| Metric | Engine Portfolio | Nifty 50 Benchmark |
|-|-|-|
| Total Return (Jan-Jun 2020) | **-11.78%** | -16.12% |
| Max Drawdown | **-35.80%** | -38.44% |
| Emergency Triggers | 1 | n/a |

1. Indian stocks are more correlated during crises (FII selling is indiscriminate)
2. The engine used US VIX for regime detection, missing India-specific signals
3. No India-specific emergency triggers were calibrated

## Cross-Crisis Comparison

| Metric | COVID (US) | 2022 (US) | COVID (India) |
|-|-|-|-|
| Engine Return | +12.78% | -13.36% | -11.78% |
| Benchmark Return | -4.08% | -18.67% | -16.12% |
| Alpha | **+16.86%** | **+5.31%** | **+4.34%** |
| Engine Max DD | -25.89% | -22.35% | -35.80% |
| Benchmark Max DD | -33.99% | -24.52% | -38.44% |
| DD Reduction | **8.10 pp** | **2.17 pp** | **2.64 pp** |
| Emergency Triggers | 3 | 1 | 1 |
| Crisis Detected | 9 days late | Brief (1 month only) | Dependent on US VIX |

## Key Findings

### 1. Engine handles V-shaped crashes well, grinding bears poorly
- COVID alpha: +16.86% (mean-reversion bought the dip perfectly)
- 2022 alpha: +5.31% (momentum signals fought the trend; regime whipsaw hurt)

### 2. Emergency triggers are calibrated for acute events only
- VIX >40 threshold only fires during panics (COVID Mar 2020)
- 2022 never triggered crash-buy despite -25% drawdown
- **Recommendation:** Add a cumulative drawdown trigger (portfolio -15% from peak within 60 days)

### 3. Regime detection is too slow for the first 5-10 days of a crash
- COVID: 9 trading days between peak and first crisis detection
- Estimated cost of delay: 10-15% portfolio drawdown before defensive positioning
- **Recommendation:** HMM supplementary detector (per HMM research) could reduce delay by 3-5 days

### 4. India portfolio needs independent regime detection
- Using US VIX for India regime detection misses India-specific dynamics
- India VIX spiked to 86 while US VIX was at 82, but India started from a higher base
- **Recommendation:** Add ^INDIAVIX to India regime detection; calibrate separate thresholds

### 5. HRP diversification is the primary crisis defense
- In both US crises, the 9-stock HRP allocation (overweighting low-vol JNJ, KO, COST) provided more downside protection than the signal layer
- Signal-driven alpha came almost entirely from crisis-regime mean-reversion weight

### 6. Emergency triggers fire only in extreme events
- The engine only flags VIX >40
- 2022 was a textbook buying opportunity that the engine missed
- **Recommendation:** Add "gradual accumulation" trigger for extended drawdowns (not just acute spikes)

## Recommended Engine Modifications

1. **Cumulative drawdown trigger:** If portfolio is -15% from 60-day high, fire emergency signal even if VIX <40
2. **Regime persistence filter:** Require 5 consecutive days in new regime before switching (reduces 2022 whipsaw)
3. **Low-confidence override:** When regime confidence <0.40, use previous regime (prevents ambiguous flips)
4. **India-specific VIX thresholds:** ^INDIAVIX >25 = risk_off, >35 = crisis (calibrated separately from US)
5. **Bear market momentum clamp:** When regime is risk_off for 3+ consecutive months, reduce momentum weight by 50% (prevents trend-fighting in secular bears)
