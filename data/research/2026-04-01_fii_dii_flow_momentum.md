# Signal Investigation: FII/DII Flow Momentum

**Date:** 2026-04-01

## Hypothesis

Foreign Institutional Investor (FII) flows into Indian equities are momentum-driven: sustained buying begets buying. Rolling 5/10/20-day net FII flow momentum should predict forward Nifty returns. Additionally, India's relative performance versus broader EM (INDA/EEM ratio momentum) captures India-specific capital allocation shifts beyond global EM risk appetite.

## Data

- **FII flow proxy:** INDA ETF (iShares MSCI India) signed volume flow = daily return * volume, normalized by 63-day average volume. Direct FII/DII data from NSDL/CDSL is not programmatically available via yfinance.
- **India-EM relative proxy:** INDA/EEM price ratio momentum (India vs EM allocation shift)
- **Target:** Nifty 50 (^NSEI) forward returns at 5d, 10d, 21d horizons
- **Regime variable:** India VIX (^INDIAVIX)
- **Period:** 2019-04-15 to 2026-02-25, 1,642 usable observations
- **IS/OOS Split:** 70/30 (IS: 1,149 obs to 2024-01-31, OOS: 493 obs from 2024-02-01)

## Information Coefficient Analysis

### INDA/EEM Ratio Momentum (India-specific flow direction)

| Signal | Horizon | IS IC | IS t | IS p | OOS IC | OOS t | OOS p |
|-|-|-|-|-|-|-|-|
| inda_eem_mom_5d | nifty_fwd_5d | 0.0642 | 2.18 | 0.029 | **0.0998** | **2.22** | **0.027** |
| inda_eem_mom_5d | nifty_fwd_10d | 0.0174 | 0.59 | 0.557 | **0.1010** | **2.25** | **0.025** |
| inda_eem_mom_5d | nifty_fwd_21d | 0.0559 | 1.90 | 0.058 | **0.1739** | **3.91** | **0.0001** |
| inda_eem_mom_10d | nifty_fwd_21d | 0.0750 | 2.54 | 0.011 | **0.1510** | **3.39** | **0.0008** |
| inda_eem_mom_20d | nifty_fwd_5d | 0.0754 | 2.55 | 0.011 | **0.1456** | **3.26** | **0.001** |
| inda_eem_mom_20d | nifty_fwd_10d | 0.0658 | 2.22 | 0.027 | **0.1759** | **3.96** | **0.00009** |
| inda_eem_mom_20d | nifty_fwd_21d | 0.0423 | 1.43 | 0.154 | **0.2422** | **5.53** | **<0.001** |

**The INDA/EEM ratio momentum is the clear winner.** Consistent positive sign IS and OOS across ALL signal/horizon combinations. OOS ICs are stronger than IS (0.10-0.24 OOS vs 0.02-0.08 IS), which is unusual and suggests the signal strengthened in the 2024-2026 period.

Best combination: **inda_eem_mom_20d vs nifty_fwd_21d** with OOS IC = 0.2422.

### Direct Flow Momentum (INDA signed volume)

| Signal | Horizon | IS IC | IS p | OOS IC | OOS p |
|-|-|-|-|-|-|
| flow_mom_5d | nifty_fwd_21d | 0.0872 | 0.003 | -0.0352 | 0.436 |
| flow_mom_10d | nifty_fwd_10d | 0.0400 | 0.175 | **-0.1494** | **0.001** |
| flow_mom_20d | nifty_fwd_10d | 0.0830 | 0.005 | **-0.2005** | **<0.001** |
| flow_mom_20d | nifty_fwd_21d | 0.0980 | 0.001 | **-0.1590** | **<0.001** |

**SIGN FLIP: Direct flow momentum flips from positive IS to negative OOS.** This means INDA volume flow momentum predicted Nifty returns positively in-sample (2019-2024) but negatively out-of-sample (2024-2026). This is a classic overfitting signature for the direct flow measure. The flow_mom signals are REJECTED.

## Rolling ICIR

| Signal | Mean Rolling IC | Std | ICIR | % Positive |
|-|-|-|-|-|
| flow_mom_10d | -0.0736 | 0.2316 | **-0.318** | 37.7% |
| inda_eem_mom_10d | -0.0214 | 0.3657 | -0.058 | 46.2% |

Rolling ICIR is weak for both signals. The inda_eem signal has near-zero ICIR in rolling 63-day windows, meaning its OOS IC strength may be driven by a specific regime (2024-2026 India outperformance vs EM) rather than a persistent relationship. This is a concern.

## Quintile Analysis (21d Forward Nifty Returns)

### inda_eem_mom_10d

| Quintile | IS Mean | IS Std | OOS Mean | OOS Std |
|-|-|-|-|-|
| Q1 (India underperforming EM) | 1.16% | 6.83% | 0.01% | 3.92% |
| Q2 | 0.88% | 6.49% | 0.29% | 2.98% |
| Q3 | 1.35% | 6.14% | -0.64% | 2.90% |
| Q4 | 1.37% | 4.70% | 0.60% | 2.89% |
| Q5 (India outperforming EM) | **2.07%** | 4.49% | **1.71%** | 4.15% |

Q5 is the clear winner in both IS and OOS. IS shows weak monotonicity (Q1-Q3 jumbled, but Q4-Q5 are highest). OOS shows better separation at the extremes (Q5 >> Q1) but Q3 is anomalously negative. The Q5-Q1 spread is 0.91% IS and 1.70% OOS per 21 days.

**Not monotonic enough for high confidence.** The middle quintiles are noisy, and the Q3 OOS anomaly is concerning.

## Regime Analysis

### inda_eem_mom_10d

| Regime | n | IC | p-value |
|-|-|-|-|
| Low India VIX (< 15) | 779 | **0.2558** | **<0.001** |
| Normal (15-25) | 732 | 0.0222 | 0.548 |
| High India VIX (>= 25) | 124 | **-0.3028** | **0.001** |

**Extreme regime dependency.** The signal is strongly positive in calm markets (IC=0.26) and strongly NEGATIVE in high-vol markets (IC=-0.30). In normal conditions, the signal is essentially zero. This means India EM-relative momentum works as a trend signal in calm markets but is a contrarian (wrong-direction) signal during crises.

### flow_mom_10d

| Regime | n | IC | p-value |
|-|-|-|-|
| Low VIX | 779 | 0.0595 | 0.097 |
| Normal | 733 | **0.1210** | **0.001** |
| High VIX | 124 | -0.1103 | 0.223 |

Flow momentum works best in normal vol conditions but fails in both extremes.

## Per-Stock OOS IC (flow_mom_10d)

| Ticker | OOS IC | p-value |
|-|-|-|
| RELIANCE.NS | -0.1185 | 0.008 |
| TCS.NS | -0.1286 | 0.004 |
| HDFCBANK.NS | -0.1301 | 0.004 |
| ICICIBANK.NS | -0.1065 | 0.018 |
| LT.NS | -0.1103 | 0.014 |
| SBIN.NS | -0.0596 | 0.186 |
| INFY.NS | -0.0176 | 0.696 |
| ITC.NS | 0.0492 | 0.276 |
| HINDUNILVR.NS | -0.0191 | 0.672 |
| BHARTIARTL.NS | -0.0188 | 0.677 |

**Negative OOS IC for most stocks** when using direct flow momentum. Banks and large-caps show the strongest (negative) relationship. This confirms the sign flip: INDA buying flow in 2024-2026 was NOT predictive of positive individual stock returns.

## Signal Correlations

| Signal Pair | Spearman Correlation |
|-|-|
| flow_mom_10d vs Nifty 12m momentum | -0.005 |
| flow_mom_10d vs USDINR 21d momentum | **-0.308** |
| flow_mom_10d vs India VIX | -0.058 |

The -0.31 correlation with USDINR confirms the prior concern: FII flows are partly a dollar proxy. When FIIs buy (positive flow), the rupee strengthens (USDINR falls), creating correlation. The inda_eem signal partially controls for this by measuring India-SPECIFIC allocation vs EM.

## Bonferroni Correction (27 tests)

| Signal | Horizon | Raw p | Bonferroni p | Sig@5% |
|-|-|-|-|-|
| inda_eem_mom_20d | nifty_fwd_21d | <0.001 | **0.000001** | **YES** |
| flow_mom_20d | nifty_fwd_10d | <0.001 | **0.000195** | **YES** |
| inda_eem_mom_20d | nifty_fwd_10d | <0.001 | **0.002338** | **YES** |
| inda_eem_mom_5d | nifty_fwd_21d | 0.0001 | **0.002808** | **YES** |
| flow_mom_20d | nifty_fwd_21d | 0.0004 | **0.010649** | **YES** |
| inda_eem_mom_10d | nifty_fwd_21d | 0.0008 | **0.020739** | **YES** |

Six signal/horizon combinations survive Bonferroni. The inda_eem_mom signals dominate.

## Transaction Cost Sensitivity

The INDA/EEM ratio is a macro regime signal, not a stock-level trading signal. Implementation as a regime overlay or tilt modifier adds minimal turnover:
- INDA/EEM 20-day momentum changes sign ~6-8 times per year
- At monthly rebalance, this adds ~2-4 additional tilt changes per year
- Estimated additional annual turnover: 8-15%
- At 15bps per side: 2.4-4.5 bps annual cost. Negligible.

## Verdict: MIXED, Partial PROMISING, Partial REJECTED

### REJECTED: Direct Flow Momentum (flow_mom)
- IS/OOS sign flip is disqualifying
- Negative rolling ICIR
- Per-stock OOS IC is negative
- The direct volume-flow proxy is not reliable

### PROMISING (with caveats): INDA/EEM Ratio Momentum (inda_eem_mom)
**Reasons for provisional acceptance:**
1. Consistent positive IC sign IS and OOS across all horizons
2. OOS IC of 0.24 (20d signal, 21d horizon) is strong
3. Survives Bonferroni at 0.1% level
4. Low correlation with existing signals
5. Trivially available data (INDA, EEM already on yfinance)

**Serious concerns:**
1. **Rolling ICIR near zero (-0.06)**, the period-by-period consistency is very weak despite high aggregate OOS IC. This suggests the OOS IC is driven by a specific regime (India outperformance 2024-2026) rather than a stable relationship.
2. **Extreme regime dependency**, the signal REVERSES in high-VIX periods (IC=-0.30). A regime-conditional implementation is mandatory.
3. **Not a true FII/DII flow measure**, the INDA/EEM ratio is a price-based relative momentum signal, not actual institutional flow data. The hypothesis (FII flows drive returns) is tested only via proxy.
4. **OOS period specificity**, India massively outperformed EM in 2024-2026 (AI/services boom, domestic consumption growth). The signal may be capturing a one-time allocation shift, not a repeatable pattern.

**Requirements before implementation:**
1. Walk-forward validation (same protocol as Cu/Au)
2. Obtain actual FII/DII daily flow data from NSE/NSDL for proper signal construction
3. Test on pre-2019 data (India has FII flow data back to 2005)
4. Regime-conditional implementation only (zero weight when India VIX >= 25)
