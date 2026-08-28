# Signal Research: FII Flow Deep Dive (India)

Date: 2026-04-01
Universe: India (20 NSE tickers)
FII Proxy: INDA ETF (iShares MSCI India) volume and INDA/EEM ratio
Benchmark: Nifty 50 (^NSEI)

## Background

The earlier study (2026-04-01_fii_dii_flow_momentum.md) showed the INDA/EEM ratio as promising but needing more work.
This deep dive tests multiple formulations of INDA volume as an FII flow proxy:
1. Volume z-score (high/low volume regimes)
2. INDA/EEM ratio momentum (21d and 63d)
3. Volume momentum (accelerating/decelerating inflows)
4. Extreme volume mean-reversion
5. Cross-sectional: does INDA volume predict IT vs Banks differently?

## Rationale

INDA is the largest India-focused ETF traded in US markets.
Its volume reflects foreign institutional investor (FII) activity:
- High INDA volume = FII actively trading India exposure
- INDA/EEM ratio rising = India gaining relative allocation within EM
- Volume momentum = trend in FII interest

## Test 1: INDA Volume Z-Score vs Forward Nifty Returns

| INDA Vol Z-Score | Fwd Horizon | Fwd Nifty Return | Rho | p-value |
|-|-|-|-|-|
| continuous | 10d | high=0.0377%, low=0.0333% | 0.0309 | 0.202 |
| continuous | 1d | high=-0.0414%, low=0.0327% | -0.0192 | 0.428 |
| continuous | 21d | high=0.0977%, low=-0.0025% | 0.0015 | 0.9509 |
| continuous | 5d | high=-0.0331%, low=0.0733% | -0.0166 | 0.4934 |

## Test 2: INDA/EEM Ratio Momentum vs Forward Nifty

| Signal | Fwd Horizon | Rho | p-value | Significant? |
|-|-|-|-|-|
| INDA/EEM 21d_mom | 10d | 0.0451 | 0.0585 | YES |
| INDA/EEM 21d_mom | 21d | 0.0078 | 0.7438 | NO |
| INDA/EEM 21d_mom | 42d | 0.0488 | 0.0425 | YES |
| INDA/EEM 21d_mom | 5d | 0.0459 | 0.0542 | YES |
| INDA/EEM 63d_mom | 10d | 0.0268 | 0.2676 | NO |
| INDA/EEM 63d_mom | 21d | 0.0161 | 0.5066 | NO |
| INDA/EEM 63d_mom | 42d | 0.0233 | 0.3399 | NO |
| INDA/EEM 63d_mom | 5d | 0.0399 | 0.0983 | YES |

## Test 3: INDA Volume Momentum vs Forward Nifty

| Signal | Fwd Horizon | Rho | p-value | Significant? |
|-|-|-|-|-|
| vol_mom_10d | 10d | 0.0097 | 0.6898 | NO |
| vol_mom_10d | 21d | -0.0022 | 0.9263 | NO |
| vol_mom_10d | 5d | 0.0161 | 0.5057 | NO |
| vol_mom_20d | 10d | -0.0006 | 0.9796 | NO |
| vol_mom_20d | 21d | -0.0236 | 0.3354 | NO |
| vol_mom_20d | 5d | -0.0094 | 0.7005 | NO |
| vol_mom_5d | 10d | 0.0074 | 0.758 | NO |
| vol_mom_5d | 21d | -0.0256 | 0.2908 | NO |
| vol_mom_5d | 5d | -0.0091 | 0.705 | NO |

## Test 4: Extreme Volume Events (Mean-Reversion)

| Condition | Fwd Horizon | Mean Fwd Return | Baseline | n Events |
|-|-|-|-|-|
| extreme_high_vol_z1.5_10d | - | -0.0216% | 0.0426% | 177 |
| extreme_high_vol_z1.5_21d | - | 0.1115% | 0.0419% | 176 |
| extreme_high_vol_z1.5_5d | - | 0.0639% | 0.0445% | 177 |
| extreme_high_vol_z2.0_10d | - | 0.1207% | 0.0426% | 91 |
| extreme_high_vol_z2.0_21d | - | 0.0012% | 0.0419% | 91 |
| extreme_high_vol_z2.0_5d | - | 0.2621% | 0.0445% | 91 |
| extreme_low_vol_z1.5_10d | - | 0.1359% | 0.0426% | 48 |
| extreme_low_vol_z1.5_21d | - | -0.0253% | 0.0419% | 48 |
| extreme_low_vol_z1.5_5d | - | 0.1275% | 0.0445% | 48 |

## Test 5: Sector-Specific Effects

| INDA Vol vs | Fwd Horizon | Rho | p-value | Significant? |
|-|-|-|-|-|
| Banks sector | 10d | 0.0326 | 0.1891 | NO |
| Banks sector | 21d | 0.0326 | 0.1906 | NO |
| Banks sector | 5d | 0.007 | 0.7765 | NO |
| IT sector | 10d | 0.0213 | 0.3914 | NO |
| IT sector | 21d | -0.0219 | 0.38 | NO |
| IT sector | 5d | 0.007 | 0.7788 | NO |

## Multiple Testing Adjustment

Total tests conducted: 27
Significant at 10% level: 4
Expected false positives at 10%: 2.7

## Verdict

**WEAK PASS**: Some signal detected but not strong enough for standalone use.
The INDA volume proxy captures some FII activity but is noisy.
Recommend collecting actual FII/DII daily data from NSE for direct testing.

## Implementation Notes

If implementing:
- Signal should be regime overlay, not stock-level signal
- INDA/EEM ratio momentum is cleaner than raw volume
- Volume data is free and available via yfinance
- For production: supplement with actual FII data from NSE website
