# Research Studies

Each study below is a markdown write-up. Scripts (`*.py`) regenerate the study that names them; they are run from the repository root with the project virtualenv and resolve paths through `quantshield.paths`. Raw outputs are the `*.json` files. Verdicts are summarized in `signal_ledger.json`, which is the trial count used by the deflated Sharpe ratio. The consolidated report is `docs/research_report.pdf`.

## Signal studies, US

| Study | One line | Verdict |
|-|-|-|
| `2026-04-01_vix_term_structure.md` | VIX/VIX3M ratio vs forward SPY returns; strong in stress, dead in 2023, reversed in 2026 | conditional, not deployed |
| `2026-04-01_put_call_ratio.md` | CBOE put/call unavailable; VIX-percentile and SKEW proxies show no IS significance | rejected |
| `2026-04-01_insider_trading.md` | 6 insider purchases in 2 years across 9 mega-caps; nothing to test | rejected |
| `2026-04-01_credit_spreads.md` | HYG/LQD spread variants collapse or flip sign out of sample | rejected |
| `2026-04-01_sector_relative_strength.md` | Sector ETF momentum flips sign OOS across all variants | rejected |
| `2026-04-01_breadth_indicators.md` | Share of stocks above 50-day SMA: raw ICIR -1.45 but 0.77 correlation with trend | see multivariate follow-up |
| `2026-04-01_breadth_multivariate.md` | Breadth level is redundant (VIF 4.20); breadth momentum's 33x IS-to-OOS jump is an artifact | rejected (both) |
| `2026-04-01_options_skew.md` | SKEW variants sign-flip between IS and OOS; prohibitive turnover | rejected |
| `2026-04-01_short_interest.md` | No historical short-interest series; volume proxy has no power | rejected |
| `2026-04-01_variance_risk_premium.md` | Implied minus realized vol: no OOS IC, negative in low-VIX regimes | rejected |
| `2026-04-01_bond_equity_correlation.md` | SPY/TLT correlation z-score flips sign IS to OOS | rejected |
| `2026-04-01_copper_gold_ratio.md` | Inverted copper/gold momentum: consistent IS/OOS sign, monotonic OOS quintiles | promising, see walk-forward |
| `2026-04-01_copper_gold_walk_forward.md` | WF ICIR 0.355, p 0.0036; survives Bonferroni-14 at exactly 5% | conditional, not deployed |
| `2026-04-01_earnings_revision_momentum.md` | Price-target revisions flip sign OOS; action count untested in walk-forward | rejected |
| `2026-04-01_analyst_estimate_dispersion.md` | Single cross-section of 9 targets; cannot be backtested | rejected |
| `2026-04-01_seasonality_signals.md` | US calendar effects all p > 0.35; India turn-of-month p 0.011, fails Bonferroni | rejected (US), conditional timing rule (India) |
| `2026-04-01_hmm_regime_detection.md` | 3-state HMM degenerates; 7x the transitions of the VIX heuristic | rejected as production feature |
| `2026-04-02_move_vix_divergence.md` | MOVE/VIX z-score IC near zero at 5 and 21 days | rejected |
| `2026-04-02_factor_crowding.md` | 12-1 L/S Sharpe 0.164 over 5 years; equal-weight universe 0.77 correlated with MTUM | analysis; 3-1 claim withdrawn |

## Signal studies, India

| Study | One line | Verdict |
|-|-|-|
| `2026-04-01_currency_momentum_inr.md` | USDINR momentum flips sign OOS; no incremental IC over UUP | rejected |
| `2026-04-01_fii_dii_flow_momentum.md` | Direct flow proxy flips sign; INDA/EEM ratio has OOS IC 0.24 but rolling ICIR near zero | rejected, never walk-forward tested |
| `2026-04-01_fii_flow_deep_dive.md` | 27 INDA volume formulations; 4 significant at 10%, 2.7 expected by chance | rejected |
| `midcap-momentum-study.md` | Momentum on 29 NSE midcaps loses to equal weight at every lookback | rejected |
| `multi-asset-regime-timing.md` | Regime detector timing equity, gold and liquid: no significant gain, crisis flags are contrarian | rejected |
| `country-rotation-study.md` | Country ETF momentum: full-sample Sharpe 0.99 decays to 0.58 walk-forward | rejected |
| `dca-crash-buy-timing.md` | Doubling contributions on VIX spikes: no US timing value; India +10% over 18 years on two episodes | rejected, not implemented |

## Validation and construction

| Study | One line | Verdict |
|-|-|-|
| `momentum-lookback-study.md` | 2-1 to 12-1 lookbacks in walk-forward, US and India, plus a 10-year reproduction | lookback does not matter; keep 12-1 |
| `2026-04-02_portfolio_construction_comparison.md` | EW, inverse vol, ERC, HRP within 0.06 Sharpe | keep HRP; nothing beats 1/N |
| `sector-equal-weight-study.md` | Full-sample sector-equal-weight vs naive EW and market cap | superseded by deep validation |
| `sector-ew-deep-validation.md` | Walk-forward +0.066 Sharpe (India), CI includes zero; random sector maps give nothing; US -0.10 | zero-cost default, not alpha |
| `existential-experiment.md` | Equal weight vs equal weight plus risk overlay, US and India; review corrections recorded | overlay indistinguishable from 1/N |
| `existential-experiment-v2.md` | Same test with one code path for all strategies: full engine 1.247 vs EW 1.272 | engine indistinguishable from 1/N |
| `signal-rethink.md` | Factor timing, sector ETF universe, crash-buying overlays vs equal weight | all rejected |
| `stress-test-results.md` | COVID 2020, 2022 bear, India COVID replays with regime timeline | V-shaped crashes handled, grinding bears not |
| `wf-robustness-analysis.md` | Lookback and rebalance grid, Monte Carlo weight perturbation, design caveats | stable direction, not significant (US) |
| `2026-04-02_survivorship_bias.md` | Current vs historical universes: +4.1%/yr (US), +1.5%/yr (India) | quantified |
| `2026-04-02_survivorship_bias_mitigation.md` | Fallen angels, ETF benchmark, universe rotation, shorter windows | recommendations |

## Raw outputs

`deep_validation_results.json` (sector EW), `hmm_regime_raw.json`, `seasonality_raw.json`, `stress_test_raw.json`.

## Scripts

`country_rotation_study.py`, `existential_experiment.py`, `existential_experiment_v2.py`, `midcap_momentum_study.py`, `momentum_lookback_study.py`, `move_vix_and_portfolio_construction.py`, `multi_asset_regime_timing.py`, `sector_equal_weight_study.py`, `sector_ew_deep_validation.py`, `signal_rethink.py`. All download prices through yfinance and are not re-run as part of the test suite. `legacy_signals.py` keeps the vol targeting, walk-forward sector limit, spread-plus-impact cost, VIX term structure and copper/gold functions that were removed from the package, so the existential, signal-rethink and construction scripts still run as written.
