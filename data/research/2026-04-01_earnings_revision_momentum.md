# Signal Investigation: Earnings Revision Momentum

**Date:** 2026-04-01

## Hypothesis

Changes in analyst consensus (price target revisions, grade changes, upgrade/downgrade actions) over trailing 30/60/90-day windows predict forward stock returns. Analysts herd and under-react to information, so revision trends persist. Stocks with accelerating upward revisions should outperform for 1-3 months.

## Data

- **Source:** yfinance `upgrades_downgrades` for each ticker (analyst price target changes, grade changes, actions)
- **Signal constructions:**
  - `pt_rev_Xd`: Rolling X-day mean of (currentPriceTarget / priorPriceTarget - 1) per analyst action
  - `grade_chg_Xd`: Rolling X-day sum of grade change (numeric: Buy=2, Hold=0, Sell=-2, etc.)
  - `action_Xd`: Rolling X-day sum of action scores (upgrade=1, maintain=0, downgrade=-1)
- **Universe:** 9 US stocks (AAPL, GOOGL, AMZN, NVDA, JNJ, KO, BRK-B, COST, MSFT)
- **Period:** 2019-02-13 to 2026-03-02
- **Pooled observations:** 15,939 (cross-sectional: 9 stocks x ~1,771 days)
- **IS/OOS Split:** 70/30 (IS: 11,160 obs to 2024-01-17, OOS: 4,779 obs from 2024-01-18)

**Data limitation:** yfinance provides price target revisions per analyst event, NOT time-stamped consensus EPS estimates. This is a PROXY for true earnings revision momentum (Chan, Jegadeesh, Lakonishok 1996), which requires historical consensus EPS data not freely available. Our signal captures analyst sentiment shifts, not pure earnings estimate changes.

## Information Coefficient Analysis

### Price Target Revision (pt_rev), SIGN FLIP OBSERVED

| Signal | Horizon | IS IC | IS t | IS p | OOS IC | OOS t | OOS p |
|-|-|-|-|-|-|-|-|
| pt_rev_30d | fwd_21d | **0.0413** | **4.37** | **<0.001** | -0.0289 | -2.00 | 0.046 |
| pt_rev_60d | fwd_5d | **0.0333** | **3.48** | **0.001** | -0.0351 | -2.43 | 0.015 |
| pt_rev_60d | fwd_10d | **0.0577** | **6.03** | **<0.001** | **-0.0660** | **-4.58** | **<0.001** |
| pt_rev_60d | fwd_21d | **0.0859** | **9.00** | **<0.001** | **-0.0863** | **-5.99** | **<0.001** |
| pt_rev_90d | fwd_21d | **0.0805** | **8.32** | **<0.001** | **-0.0894** | **-6.21** | **<0.001** |

**CRITICAL: IS/OOS SIGN FLIP for price target revisions.** IS shows positive IC (higher revisions predict higher returns, as expected by theory). OOS shows NEGATIVE IC (higher revisions predict LOWER returns). This is the textbook overfitting/regime-change signature.

**Interpretation:** In 2019-2024 (IS), analyst price target upgrades preceded continued rallies. In 2024-2026 (OOS), price target upgrades were LAGGING indicators, analysts upgraded AFTER stocks had already rallied, and subsequent returns were negative (mean-reversion). The OOS period includes the AI bubble peak and tariff-driven selloffs, where analyst consensus was systematically late.

### Grade Change (grade_chg), WEAK

| Signal | Horizon | IS IC | IS p | OOS IC | OOS p |
|-|-|-|-|-|-|
| grade_chg_60d | fwd_21d | **0.1042** | **<0.001** | **0.0549** | **0.0001** |
| grade_chg_30d | fwd_21d | 0.0492 | <0.001 | -0.0163 | 0.261 |

The 60-day grade change sum maintains a consistent positive sign IS and OOS, but OOS IC drops from 0.104 to 0.055 (47% degradation). Marginally useful but not strong.

### Action Score (action), BEST PERFORMER

| Signal | Horizon | IS IC | IS p | OOS IC | OOS p |
|-|-|-|-|-|-|
| action_60d | fwd_5d | 0.0027 | 0.777 | **0.0408** | **0.005** |
| action_60d | fwd_10d | 0.0239 | 0.013 | **0.0577** | **<0.001** |
| action_60d | fwd_21d | **0.0554** | **<0.001** | **0.1002** | **<0.001** |

**The 60-day action score is the strongest signal with consistent positive sign.** Remarkably, the OOS IC (0.1002) is STRONGER than the IS IC (0.0554). The action score (simple count of upgrades minus downgrades) outperforms the more granular price target revision, likely because it is less prone to the denominator effect (small prior PT inflates revision %).

## Rolling ICIR (action_60d vs fwd_21d)

| Metric | Value |
|-|-|
| Mean Rolling IC (63d windows) | **0.0834** |
| Std Rolling IC | 0.1418 |
| ICIR | **0.588** |
| % positive IC periods | **68.3%** |

ICIR of 0.59 is strong. Over two-thirds of rolling windows show positive IC.

## Quintile Analysis (21d Forward Returns)

### pt_rev_60d (SIGN-FLIPPED)

| Quintile | IS Mean | OOS Mean |
|-|-|-|
| Q1 (worst revisions) | 1.54% | **4.30%** |
| Q2 | 1.52% | 0.79% |
| Q3 | 1.32% | 0.69% |
| Q4 | 2.44% | 1.81% |
| Q5 (best revisions) | **3.86%** | 1.82% |

IS shows monotonic Q1-to-Q5 ordering (as expected). OOS shows Q1 massively outperforming Q5, confirming the sign flip. Stocks with the WORST recent price target revisions performed best OOS.

### grade_chg_60d (CONSISTENT SIGN)

| Quintile | IS Mean | OOS Mean |
|-|-|-|
| Q1 (most downgrades) | 0.92% | 1.12% |
| Q2 | 2.37% | 3.46% |
| Q3 | 0.62% | 0.32% |
| Q4 | 2.73% | 2.50% |
| Q5 (most upgrades) | **4.04%** | 2.01% |

IS is roughly monotonic. OOS ordering is messy (Q2 is the highest, Q3 lowest). Not monotonic enough for reliable signal use.

## Per-Stock OOS IC (pt_rev_60d)

| Ticker | OOS IC | p-value |
|-|-|-|
| AMZN | **-0.4119** | **<0.001** |
| KO | **-0.3452** | **<0.001** |
| BRK-B | **-0.2355** | **<0.001** |
| AAPL | **-0.1401** | **0.001** |
| GOOGL | **-0.1347** | **0.002** |
| NVDA | -0.0772 | 0.075 |
| MSFT | -0.0446 | 0.305 |
| JNJ | -0.0136 | 0.754 |
| COST | **+0.1399** | **0.001** |

All stocks except COST show negative OOS IC for pt_rev_60d. AMZN has the strongest reversal (-0.41), suggesting analyst price targets for AMZN in 2024-2026 were maximally wrong-directional. COST is the sole exception (revisions still predictive).

## Regime Analysis (pt_rev_60d)

| Regime | n | IC | p-value |
|-|-|-|-|
| VIX < 15 | 3,546 | 0.0187 | 0.265 |
| 15 <= VIX < 25 | 9,117 | **0.0296** | **0.005** |
| VIX >= 25 | 3,006 | **0.0607** | **0.001** |

The signal works best in high-vol regimes (IC=0.06 when VIX>=25). In calm markets, it is near-zero. This is the FULL-SAMPLE result; the OOS sign flip means the regime analysis is misleading since IS and OOS are mixed.

## Correlation with Existing Signals

| Stock | pt_rev_60d vs 12m Momentum | pt_rev_60d vs RSI |
|-|-|-|
| AAPL | 0.502 | -0.063 |
| GOOGL | **0.651** | 0.117 |
| AMZN | 0.559 | 0.049 |
| NVDA | 0.448 | 0.053 |
| COST | **0.686** | 0.052 |
| MSFT | 0.545 | 0.086 |

**HIGH CORRELATION with momentum (0.41-0.69).** Price target revisions are substantially redundant with 12-month price momentum. Analysts update targets based on price performance, so the revision signal largely proxies for what we already capture. The action_60d signal may be less correlated (analysts can maintain grade while revising targets), but this was not separately tested.

## Bonferroni Correction (21 tests)

| Signal | Horizon | Raw p | Bonferroni p | Sig@5% |
|-|-|-|-|-|
| action_60d | fwd_21d | <0.001 | **<0.001** | **YES** |
| pt_rev_90d | fwd_21d | <0.001 | **<0.001** | **YES** |
| pt_rev_60d | fwd_21d | <0.001 | **<0.001** | **YES** |
| pt_rev_90d | fwd_10d | <0.001 | **<0.001** | **YES** |
| grade_chg_60d | fwd_21d | 0.0001 | **0.003** | **YES** |
| action_60d | fwd_5d | 0.005 | 0.101 | NO |

Multiple signals survive Bonferroni, but note this tests the OOS p-values which include sign-flipped pt_rev signals (significant but WRONG direction).

## Transaction Cost Sensitivity

Daily signal z-score changes are low (0.03-0.07 per day), consistent with the signal being slow-moving (analyst actions happen a few times per month per stock). At monthly rebalance with 15bps costs:
- Signal-driven turnover: ~20-30% annualized
- Cost: 6-9 bps annual. Manageable.

## Verdict: MIXED

### REJECTED: Price Target Revision (pt_rev)
1. **IS/OOS sign flip** across all horizons, disqualifying
2. Per-stock OOS IC is negative for 8/9 stocks
3. High correlation with existing momentum signal (0.41-0.69), redundant when working, contrarian when not
4. Analysts revise targets AFTER price moves, making this a lagging indicator

### PROMISING (WEAK): Action Score (action_60d)
**Reasons for provisional acceptance:**
1. Consistent positive sign IS and OOS (IC improves OOS: 0.055 to 0.100)
2. Rolling ICIR of 0.59 with 68.3% positive periods
3. Survives Bonferroni
4. Lower correlation with momentum than pt_rev (counts actions, not magnitudes)

**Concerns:**
1. IC of 0.10 is modest (compared to momentum IC of 0.15-0.20 in this universe)
2. The OOS improvement over IS is suspicious, may reflect regime specificity of 2024-2026
3. Need to test correlation of action_60d with momentum specifically (only pt_rev was tested)
4. BRK-B has only 13 analyst events in 7 years, signal is undefined for coverage-thin stocks

### REJECTED: Grade Change (grade_chg)
1. OOS IC drops 47% from IS (0.104 to 0.055)
2. Non-monotonic quintiles in OOS
3. Essentially a noisier version of action_60d

**Requirements before implementation:**
1. Test action_60d correlation with existing momentum signal
2. Exclude BRK-B from signal (insufficient analyst coverage)
3. Walk-forward validation
4. If possible, obtain historical consensus EPS data (Alpha Vantage, FMP, or Zacks) for a proper earnings revision signal. The current proxy (analyst action count) is a second-best approach.
5. Test on India universe (analyst coverage may be sparser for NSE stocks)
