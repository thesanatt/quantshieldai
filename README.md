# QuantShieldAI

A small quant research and execution system for US and Indian equities, with a public record of what it found and what it did not.

## What it is

QuantShieldAI runs a signal and risk pipeline over a 9-stock US book and a 20-stock India book, then validates it with an expanding walk-forward backtest and a set of significance tests. A separate live loop executes a small delivery portfolio on Zerodha Kite under fixed guardrails. A pre-registered intraday study tested an opening range breakout on NIFTYBEES and closed with a negative result. The numbers below are also published at https://quantshieldai.com.

The core finding is negative: the signal stack does not beat its benchmark with statistical significance, and it does not beat equal weight. The repository is published so the method, the tests, and the live record can be read and checked.

## Results

Walk-forward numbers come from `dashboard/src/data/us.json` and `dashboard/src/data/india.json`, written by `python -m quantshield.engine` on 2026-08-28 (`generated` key). The walk-forward key is `walk_forward`; the deflated Sharpe key is `deflated_sharpe`; the factor regression key is `fama_french`.

| Metric | US (9 stocks vs S&P 500) | India (20 stocks vs Nifty 50) |
|-|-|-|
| Walk-forward window | 2020-10-06 to 2026-08-13 | 2020-10-12 to 2026-08-14 |
| Periods (21 trading days each) | 70, 0 fallbacks | 69, 0 fallbacks |
| Cost model | flat 10 bps per unit of one-way turnover | NSE CNC delivery schedule per leg |
| Win rate vs benchmark | 52.9% (37 of 70) | 55.1% (38 of 69) |
| Cumulative return, portfolio / benchmark | 209.69% / 148.63% | 142.96% / 104.51% |
| Cumulative excess return, pp | 61.06 | 38.45 |
| Sharpe, portfolio / benchmark | 1.01 / 0.74 | 0.74 / 0.49 |
| Max drawdown, portfolio / benchmark | -24.75% / -24.52% | -15.60% / -17.23% |
| Alpha t-statistic, p-value | 1.10, p = 0.273 | 1.83, p = 0.071 |
| Bootstrap 95% CI on Sharpe (10,000 resamples, net of the risk-free rate) | [0.22, 2.01] | [-0.05, 1.62] |
| Bootstrap 95% CI on alpha, pp per year | [-3.05, 10.79], includes zero | [-0.19, 6.19], includes zero |
| Deflated Sharpe p-value (N = 37 trials) | 0.397 | 0.655 |
| Six-factor alpha (Ken French data, 69 months) | 0.61% per month, t = 2.26, p = 0.024, R2 = 0.79 | no factor data |

The alpha is not statistically significant in either market. Both p-values are above 0.05, both bootstrap alpha intervals include zero, and neither Sharpe survives deflation for 37 trials. The US factor regression leaves a positive intercept on 69 monthly observations; it is one undeflated test on a universe chosen with hindsight, and the report treats it as such.

Three further checks cut against the strategy:

- Equal-weight null. `data/research/existential-experiment-v2.md` compares the full engine (signals, HRP, risk stack) with naive equal weight on the same US universe over 2016-04-04 to 2026-04-02, 107 monthly periods, identical cost and Sharpe code paths. Sharpe 1.247 for the engine against 1.272 for equal weight. The 95% bootstrap CI on the Sharpe difference (engine minus equal weight) is [-0.13, +0.19] at 5 bps spread plus square-root impact and includes zero under all three cost models tested. Equal weight had the higher annualised return (25.7% vs 22.5%).
- Survivorship. The universes were chosen with hindsight. `data/research/2026-04-02_survivorship_bias.md` rebuilds the US book from a 2021 view and measures the inflation at +0.077 Sharpe and +4.1 percentage points of annual return; India is +1.5 points a year, a floor because two delisted names could not be downloaded. Alpha versus the ETF benchmark is less exposed than absolute return, but the stock-selection part of it is still biased.
- Intraday. The pre-registered ORB study (`data/intraday/gate.json`, `dashboard/src/data/orb.json`) lost money after costs on 132 replayed sessions; the one-sided bootstrap put P(mean <= 0) at 1.0. Details below.

The deflated Sharpe ratio is computed on the walk-forward daily return series with N = 37, the number of rows in the signal ledger (`docs/signal_ledger.md`, `dashboard/src/data/ledger.json`, `quantshield/config.py:DSR_TRIALS`). N counts candidates, not the parameter variants tried inside each study, so it is a floor. The Fama-French block appears in `us.json` only when real Ken French factor data was downloaded; synthetic factor output is never published, and there is no factor library for India.

## Method

Signals, each rank-normalised to [-1, 1] across the universe:

- momentum (252-day return skipping the most recent 21 days)
- volatility-adjusted momentum (252-day return over 63-day realised volatility)
- mean reversion (14-day RSI, inverted; a series with no moves scores 0 rather than oversold)
- trend (price against 50-day and 200-day moving averages)
- cross-asset (market beta conditioned on the VIX level, plus rate and oil sensitivity for the US; USD/INR, crude and Nifty drawdown by sector for India)

A VIX term structure signal, a copper/gold ratio signal and an earnings-surprise signal were implemented and later removed; the ledger records the evidence for each.

Regime detector (`quantshield/signals/regime.py`): a rule-based classifier over VIX level and trend, gold, oil, dollar and rates for the US, and India VIX, rupee and crude for India. It outputs one of `risk_on`, `risk_off`, `crisis` with a confidence, and selects the signal weight vector from `quantshield/config.py`.

Portfolio pipeline, in order (`quantshield/research/portfolio.py`): composite signal from regime weights; hierarchical risk parity base weights (`quantshield/risk/hrp.py`); blend of HRP and signal tilt (tilt strength 0.5); weight floor and cap (US 2% to 40%, India 1% to 15%); sector cap (US 40%, India 30%); single-name cap (US 25%, India 15%) and portfolio beta cap of 1.5 (`quantshield/risk/position_limits.py`); monthly CVaR constraint at 3% (95% confidence); limits again.

Validation (`quantshield/research/backtest.py`): expanding walk-forward with a minimum of 252 training days and a 21-day step. Each period re-runs the full pipeline on training data only, buys the resulting weights, and holds them without rebalancing inside the 21-day window, so the weights drift with prices. Costs are charged at each rebalance on the turnover from the drifted end-of-window weights to the new targets; the first period charges the full purchase from cash. The US rate is 10 bps per unit of one-way turnover; India applies the NSE delivery schedule (STT, exchange and SEBI charges, GST, stamp duty, DP charge per sell) to each leg on notional capital. Tests on the monthly alpha series: a t-test and a 10,000-resample bootstrap for Sharpe and alpha, with the Sharpe interval net of the same risk-free rate as the headline Sharpe. On the daily series: a deflated Sharpe ratio with N = 37 (`quantshield/risk/deflated_sharpe.py`) and, for the US, a six-factor regression on calendar-month returns with Newey-West errors (`quantshield/signals/fama_french.py`). The survivorship study above is reported alongside rather than corrected for.

Conventions worth knowing before reading the numbers:

- Risk-free rate. The US uses the end-of-sample 10-year yield (`^TNX`) applied to every day in the series; India uses a fixed 6.5% a year. The same rate is subtracted from the portfolio and the benchmark, in the headline Sharpe and in the bootstrap interval.
- Deflated Sharpe. The variance fed to the expected-maximum formula is the estimation variance of the observed Sharpe, which is a lower bound on the variance across trials, so the reported p is a lower bound. The deflation threshold SR* is the larger of the benchmark Sharpe and the expected maximum of N null trials.
- HRP. Ward linkage on the correlation distance sqrt((1 - rho) / 2). The original HRP paper uses single linkage; the two were not compared.
- Two betas. A 126-day beta drives the US cross-asset gate and the `beta` field in the weight tables; a separate 252-day beta clipped at zero drives the portfolio beta cap.
- Within-window drift. Weights are bought at the rebalance and left alone for 21 days; period returns and turnover both reflect the drifted weights.
- Macro lag. In the research engine the India inputs CL=F and USDINR=X are lagged one day, because both print after the NSE close (`quantshield/engine.py:_lag_after_hours`). The live planner is unchanged: at 09:25 IST the prior day's bars are already the latest available.

## Live execution

The live loop trades a small delivery portfolio (CNC product) on Zerodha Kite. It is three modules:

1. `quantshield.live.planner` scores the India universe plus a NIFTYBEES core holding, sizes trades against live cash, and writes a plan file with a ticket. Minimum trade value 800 INR; positions are cut on a 20% loss; look-through exposure to financials is capped at 50%.
2. `quantshield.live.executor` reads the plan and places LIMIT orders. It defaults to dry run. Live orders require the `--dry-run` flag to be absent and both `AUTO_EXECUTE=true` and `ZERODHA_LIVE_MODE=true` in the environment. If an order placement fails ambiguously and the follow-up order-book scan also fails, the executor journals the leg as `PLACEMENT_UNVERIFIED` and sends a notification rather than retrying.
3. `quantshield.live.daemon` runs every 30 minutes under launchd. Inside 09:25 to 14:30 IST it runs the planner and executor; at 15:35 IST it records the daily NAV snapshot. It skips the executor while `data/KILL` exists and says so once a day, ignores an intraday feed heartbeat older than a day, runs the snapshot only on a fresh token, and notifies once a day if the dashboard deploy fails.

Guardrails in `quantshield/live/executor.py`: max 3,000 INR per order, max 6,000 INR turnover per day, max 6 orders per day, limit price within 1% of reference, plan older than 6 hours is rejected, LIMIT orders only, CNC only, one executor instance at a time (file lock). A file at `data/KILL` halts the executor before and during a run. The delivery cost model in `quantshield/costs.py` (STT, exchange, SEBI and stamp charges, GST, and a 15.93 INR DP charge per sell) was checked against a broker contract note. `quantshield/calendar.py` carries all 16 NSE weekday closures for 2026.

What has happened: real capital was deployed on 2026-07-20 (`account.inception_date` in `dashboard/public/live/dashboard.json`), with the opening positions placed by hand, outside the executor. The export holds 13 daily NAV snapshots from 2026-07-20 to 2026-08-05 against a NIFTYBEES benchmark bought with the same capital on the same day: portfolio +2.89%, benchmark +1.27%, max drawdown -2.40%, three positions (NIFTYBEES 49.6%, BAJFINANCE 21.1%, SBIN 20.9% of account value). What has not happened: the executor has not placed a single order (`execution.total_fills` is 0). Kite access tokens expire every day and the login step was manual. The daemon skips the planner and executor whenever the day's token is missing and sends one login reminder instead; on the one day a plan was generated (2026-07-21) it carried zero orders, so the executor was never invoked; the snapshot reads holdings through the same token, so the series stops at 2026-08-05. The last plan is dated 2026-07-21 with zero orders and one warning; the loop status in the export is idle. There is no execution journal because nothing has been executed. The public live page reports position weights, returns, drawdown, fill count and slippage; it carries no cash amounts, cost basis, client id or token state.

## Intraday study

An opening range breakout on NIFTYBEES was pre-registered in `data/intraday/gate.json` on 2026-07-21 before any session data existed: 09:15 to 09:45 IST range, one buy stop at range high plus one tick valid to 13:00, stop at the range midpoint, time exit at 15:10, 2,000 INR notional, intraday (MIS) cost model, adverse fill assumptions. The gate required 60 live paper sessions and a one-sided bootstrap p below 0.05 against an exposure-adjusted buy-and-hold benchmark.

Replay on official 1-minute candles (`dashboard/src/data/orb.json`, `data/intraday/orb_replay.json`): 132 sessions from 2026-01-05 to 2026-07-20, 43 triggered, 13 winners (30.2% win rate against a 65.1% breakeven), gross -76.75 INR, costs 85.18 INR, net -161.93 INR (-8.1% of the 2,000 INR notional), max drawdown -167.37 INR. The bootstrap statistic is the share of 10,000 resampled means of the exposure-adjusted daily delta at or below zero, P(mean <= 0) = 1.0. Verdict: negative after costs. The rules were frozen before the replay and no parameters were searched. Two dated amendments in the gate file changed the accounting without touching the rules. The first replay measured the session benchmark from the 09:15 candle open, which is the pre-open auction print; an amendment on 2026-08-28 moved it to the 09:15 bar close, which moved the exposure-adjusted delta mean from -0.0866% to -0.1214% and left the strategy figures unchanged. A second amendment on the same day records that the cost model had exempted ETF intraday sells from STT; Zerodha charges 0.025% on them. With the corrected rate, costs rose from 65.16 to 85.18 INR, net from -141.91 to -161.93 INR, max drawdown from -147.83 to -167.37 INR and the breakeven win rate from 60.8% to 65.1%; entries, exits and gross P&L did not change and P(mean <= 0) stayed at 1.0. The live paper arm collected 1 of the 60 required sessions because the feed job was never scheduled. The study is closed; the feed, paper engine and replay code remain as the record.

## Corrections made during the public release

The following were found and fixed while preparing this repository for publication, and are recorded here rather than hidden. The deflated Sharpe ratio mixed annual and per-period units and carried ad hoc terms in the expected maximum; it now works in per-period units with the standard expected-maximum formula and is computed on the walk-forward series, not the in-sample year. Volatility targeting was removed from the pipeline: renormalising to full investment after it made it a no-op. Performance attribution was removed: it was pro-rata and said nothing. Two macro overlays (VIX term structure, copper/gold ratio) were removed because they contributed zero after rank normalisation. The India walk-forward switched from a flat 15 bps to the CNC delivery schedule. The ORB benchmark open was corrected by a dated amendment in the gate file.

A second review pass found seven more. The walk-forward had reset weights to their targets every day inside a test window, charged turnover from those targets and charged nothing for the first purchase; it now lets weights drift within the window and charges turnover from the drifted weights, including the initial purchase from cash. The bootstrap Sharpe interval was computed on raw period returns while the headline Sharpe was net of the risk-free rate; both now subtract the same rate. The India macro inputs CL=F and USDINR=X were read on the day they print, which is after the NSE close; the research engine now lags them one day. The CVaR constraint treated a tail made up entirely of gains as a breach because of a sign error; it no longer does. The RSI signal returned the oversold extreme for a series with no moves; it now returns 0. The intraday cost model charged no STT on ETF sells; the rate is now 0.025%, and the ORB figures above carry it. The deflated Sharpe ratio is now documented as a lower bound on p, because its variance input is the estimation variance of the observed Sharpe rather than the cross-trial variance, and its threshold is the larger of the benchmark Sharpe and the expected maximum. Every number in this file was regenerated after these changes.

## Layout

```
quantshield/
  engine.py              research engine CLI, --market us|india, writes dashboard/src/data/<market>.json
  config.py              universes, regime weight tables, sector maps, risk parameters, DSR_TRIALS
  calendar.py            US and India holiday and market-hours checks
  costs.py               Zerodha delivery and intraday cost model
  paths.py               repository paths
  utils.py               logging to stderr, IST helpers, atomic JSON writes, rank normalisation
  signals/               momentum, mean reversion, trend, cross-asset, composite, regime, Fama-French
  risk/                  HRP, position and beta limits, CVaR, correlation, drawdown, deflated Sharpe
  research/              walk-forward backtest and bootstrap, portfolio pipeline, track record
  broker/                Zerodha Kite and Alpaca clients (token handling, holdings, order helpers)
  live/                  planner, executor, daemon, notify, export
  intraday/              1-minute feed, candle backfill, ORB paper engine, replay, scoreboard, stats
dashboard/               React site built with Vite; reads dashboard/src/data and public/live
data/intraday/           pre-registered gate and replay output (committed)
data/research/           study notes, scripts and the signal ledger
docs/                    research report (LaTeX source and PDF) and the signal ledger
scripts/                 launchd install, dashboard deploy, intraday session wrapper
tests/                   pytest and hypothesis suites
```

## Run it

```
make setup          venv, Python and dashboard dependencies
make test           pytest, no network needed
make lint           ruff check
make engine-us      research engine, US book (downloads prices from Yahoo Finance)
make engine-india   research engine, India book
make plan           live planner, no notifications
make execute-dry    executor in dry run
make export         write the public live JSON
make dashboard      build the site
make deploy         export, copy the report, build and deploy the site
make replay         re-run the ORB replay (needs candles fetched with --fetch and a Kite token)
make report         build docs/research_report.pdf
```

Direct commands:

```
scripts/launchd.sh monitor install|uninstall|status          daemon as a launchd job (feed likewise)
python -m quantshield.broker.zerodha login-url|complete <request_token>|status   daily Kite token
python -m quantshield.broker.alpaca --weights <file> [--execute] US paper book, dry run by default
python -m quantshield.intraday.replay --candles-dir <dir>       ORB replay on locally fetched candles (not committed; --fetch needs a Kite token)
```

Requires Python 3.12 or newer and Node 22 or newer. Kite and Alpaca keys are optional; without them the research engine still runs and the live modules exit in dry run. Copy `.env.example` to `.env` to set keys. `AUTO_EXECUTE` and `ZERODHA_LIVE_MODE` default to false and no Makefile target sets them.

## Documents

- `docs/research_report.pdf` (source `docs/research_report.tex`): method, every signal study, validation results, the live safety model and the intraday study, with all engine-run numbers in one macro block at the top of the source.
- `docs/signal_ledger.md`: the 37 candidates with the statistic that decided each one; mirrored in `data/research/signal_ledger.json` and `dashboard/src/data/ledger.json`.
- `data/research/README.md`: index of the study notes and the scripts that regenerate them.

## Data and privacy

Runtime state is not committed: `data/portfolio`, `data/monitor`, `data/journal`, broker tokens, kill files and intraday ticks are all in `.gitignore`. The committed data is the research engine output in `dashboard/src/data`, the pre-registered intraday gate and replay in `data/intraday`, and the study notes in `data/research`. The public live JSON is built from local state by `quantshield.live.export`, contains weights and returns only, and is deployed with the site rather than committed.

## License

MIT. See `LICENSE`.
