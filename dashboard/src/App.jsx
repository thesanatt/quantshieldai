import { useEffect, useState } from 'react'
import us from './data/us.json'
import india from './data/india.json'
import Chart, { extent } from './components/Chart'
import Table from './components/Table'
import { StatRow } from './components/Stat'
import { ci, dateOnly, get, isNum, num, pText, pct, pval, text, tone, yesNo } from './fmt'

const optional = import.meta.glob('./data/*.json', { eager: true, import: 'default' })
const orb = optional['./data/orb.json'] || {}
const ledger = Array.isArray(optional['./data/ledger.json']) ? optional['./data/ledger.json'] : []
const markets = [
  { label: 'US', data: us },
  { label: 'India', data: india },
]
const wf = (m) => get(m, 'walk_forward', {})
const sigText = (v) => (v === true ? 'statistically significant at the 5% level' : v === false ? 'not statistically significant at the 5% level' : 'significance n/a')
const verdict = () => text(orb.verdict).replace(/\.+$/, '')
const zeroText = (v) => (v === true ? 'includes zero' : v === false ? 'excludes zero' : 'zero coverage n/a')
const regimeText = (m) => `${text(get(m, 'regime.detected')).replace('_', ' ')} (confidence ${num(get(m, 'regime.confidence'), 2)}, VIX ${num(get(m, 'regime.vix'), 1)})`

function useLive() {
  const [live, setLive] = useState(null)
  useEffect(() => {
    let active = true
    const load = () =>
      fetch('/live/dashboard.json', { cache: 'no-store' })
        .then((r) => (r.ok ? r.json() : null))
        .then((d) => active && d && setLive(d))
        .catch(() => {})
    load()
    const timer = setInterval(load, 60000)
    return () => {
      active = false
      clearInterval(timer)
    }
  }, [])
  return live
}

function Header({ asOf }) {
  return (
    <header>
      <h1>QuantShieldAI</h1>
      <p className="lede">Systematic equity research and live execution, US and India.</p>
      <p className="muted">As of {asOf}.</p>
      <nav className="nav">
        <a href="https://github.com/thesanatt/quantshieldai">GitHub repository</a>
        <a href="/research_report.pdf">Research report (PDF)</a>
      </nav>
    </header>
  )
}

function Findings() {
  const equal = ledger.find((row) => /equal.?weight|1\/N/i.test(`${row.name} ${row.hypothesis}`))
  const ratio = (v) => (isNum(v) && isNum(orb.notional) && orb.notional !== 0 ? pct((v / orb.notional) * 100) : 'n/a')
  return (
    <section>
      <h2>Findings</h2>
      <ol className="findings">
        <li>
          {markets.map(({ label, data }, i) => (
            <span key={label}>
              {i > 0 ? ' ' : ''}
              {label} walk-forward alpha over {get(data, 'benchmark.label', 'the benchmark')} is {pct(wf(data).alpha, 1, true)} across{' '}
              {num(wf(data).total_periods, 0)} periods (t = {num(wf(data).alpha_t_stat, 2)}, {pText(wf(data).alpha_p_value)}),{' '}
              {sigText(wf(data).alpha_significant)}.
            </span>
          ))}
        </li>
        <li>
          {markets.map(({ label, data }, i) => (
            <span key={label}>
              {i > 0 ? ' ' : ''}
              {label}: bootstrap alpha interval {ci(get(wf(data), 'bootstrap_ci.alpha_ci'))} {zeroText(get(wf(data), 'bootstrap_ci.alpha_includes_zero'))};{' '}
              {isNum(get(data, 'deflated_sharpe.p_value'))
                ? `deflated Sharpe ${pText(get(data, 'deflated_sharpe.p_value'))} over ${num(get(data, 'deflated_sharpe.n_trials'), 0)} trials`
                : 'deflated Sharpe not computed'}
              .
            </span>
          ))}
          {equal ? ` Against equal weight (1/N): ${text(equal.key_statistic)}.` : ''}
        </li>
        <li>
          Pre-registered ORB study: {num(orb.sessions, 0)} sessions, {num(orb.triggered, 0)} triggered, win rate {pct(orb.win_rate_pct)} against a breakeven of{' '}
          {pct(orb.breakeven_win_rate_pct)}, net {ratio(orb.net)} of per-trade notional after costs, bootstrap {pText(orb.bootstrap_p)}. Verdict: {verdict()}.
        </li>
      </ol>
    </section>
  )
}

const ageText = (minutes) => {
  if (!isNum(minutes)) return 'n/a'
  if (minutes >= 1440) return `${num(minutes / 1440, 0)} days`
  if (minutes >= 60) return `${num(minutes / 60, 0)} h`
  return `${num(minutes, 0)} min`
}

function Live({ live }) {
  const m = get(live, 'metrics', {})
  const ex = get(live, 'execution', {})
  const mon = get(live, 'monitor', {})
  const plan = get(live, 'plan', {})
  const guard = get(ex, 'guardrails', {})
  const status = text(mon.loop_status)
  const guardRows = [
    ['Max order value', num(guard.max_order_value, 0)],
    ['Max day turnover', num(guard.max_day_turnover, 0)],
    ['Max orders per day', num(guard.max_orders_per_day, 0)],
    ['Limit band', pct(guard.limit_band_pct)],
    ['Max plan age', isNum(guard.max_plan_age_h) ? `${guard.max_plan_age_h} h` : 'n/a'],
    ['Order type', text(guard.order_type)],
    ['Product', text(guard.product)],
  ].map(([limit, value]) => ({ key: limit, limit, value }))
  return (
    <section>
      <h2>Live account</h2>
      {!live && <p className="muted">Live export not loaded. The page retries every 60 seconds.</p>}
      <p>
        {text(get(live, 'account.broker'))}, {text(get(live, 'account.product'))}. Inception {dateOnly(get(live, 'account.inception_date'))}, {num(get(live, 'account.days_live'), 0)} days live.
        Last snapshot {dateOnly(lastSnapshot)}. Quotes: {live ? (live.quotes_live ? 'live' : 'from last export') : 'n/a'}. Benchmark: NIFTYBEES units bought with the same capital at inception.
      </p>
      <Chart title="Indexed NAV" rows={get(live, 'series.equity_curve', [])} labels={['Portfolio', 'NIFTYBEES']} yLabel="Inception = 100" />
      <StatRow
        items={[
          { label: 'Return', value: pct(m.total_return_pct, 2, true), tone: tone(m.total_return_pct) },
          { label: 'NIFTYBEES return', value: pct(m.bench_return_pct, 2, true) },
          { label: 'Alpha', value: pct(m.alpha_pct, 2, true), tone: tone(m.alpha_pct) },
          { label: 'Max drawdown', value: pct(m.max_drawdown_pct, 2) },
          { label: 'Day change', value: pct(m.day_change_pct, 2, true), tone: tone(m.day_change_pct) },
          { label: 'Days live', value: num(get(live, 'account.days_live'), 0) },
          { label: 'Fills', value: num(ex.total_fills, 0) },
          { label: 'Avg slippage', value: isNum(ex.avg_slippage_bps) ? `${num(ex.avg_slippage_bps, 1)} bps` : 'n/a' },
        ]}
      />
      <div className="cols">
        <Table
          caption="Positions"
          columns={[
            { key: 'symbol', label: 'Symbol' },
            { key: 'weight_pct', label: 'Weight', num: true, render: (r) => pct(r.weight_pct) },
          ]}
          rows={get(live, 'account.positions', [])}
        />
        <Table
          caption="Executor guardrails (values in INR where monetary)"
          columns={[
            { key: 'limit', label: 'Limit' },
            { key: 'value', label: 'Value', num: true },
          ]}
          rows={guardRows}
        />
      </div>
      <p>
        Loop status: <span className={status === 'halted' ? 'neg' : undefined}>{status}</span>. Heartbeat age: {ageText(mon.heartbeat_age_min)}. Last plan: {dateOnly(mon.last_plan_date)}.
        Current plan: {num(plan.orders, 0)} orders, {num(plan.warnings, 0)} warnings, regime {text(plan.regime).replace('_', ' ')}, orders today {num(ex.orders_today, 0)}.
      </p>
    </section>
  )
}

const shortCost = (s) => (s ? String(s).replace(/ per unit of one-way turnover$/, ' of one-way turnover').replace(/ \(.*\) on notional capital$/, '') : 'n/a')

function WalkForward() {
  const pair = (a, b, f) => `${f(a)} vs ${f(b)}`
  const rows = [
    ['Periods (wins)', (m) => `${num(wf(m).total_periods, 0)} (${num(wf(m).win_periods, 0)})`],
    ['Window', (m) => (wf(m).start && wf(m).end ? `${wf(m).start} to ${wf(m).end}` : 'n/a')],
    ['Cost model', (m) => shortCost(wf(m).cost_model)],
    ['Return vs benchmark', (m) => pair(wf(m).port_return, wf(m).bench_return, (v) => pct(v))],
    ['Sharpe vs benchmark', (m) => pair(wf(m).port_sharpe, wf(m).bench_sharpe, (v) => num(v, 2))],
    ['Max drawdown vs benchmark', (m) => pair(wf(m).port_maxdd, wf(m).bench_maxdd, (v) => pct(v))],
    ['Win rate', (m) => pct(wf(m).win_rate)],
    ['Alpha', (m) => pct(wf(m).alpha, 1, true)],
    ['Alpha t-stat', (m) => num(wf(m).alpha_t_stat, 2)],
    ['Alpha p-value', (m) => pval(wf(m).alpha_p_value)],
    ['Significant at 5%', (m) => yesNo(wf(m).alpha_significant)],
    ['Bootstrap alpha CI', (m) => ci(get(wf(m), 'bootstrap_ci.alpha_ci'))],
    ['Bootstrap Sharpe CI', (m) => ci(get(wf(m), 'bootstrap_ci.sharpe_ci'), 2)],
    ['Deflated Sharpe p-value', (m) => pval(get(m, 'deflated_sharpe.p_value'))],
    ['Deflated Sharpe trials', (m) => num(get(m, 'deflated_sharpe.n_trials'), 0)],
  ].map(([metric, f]) => ({ key: metric, metric, us: f(us), india: f(india) }))
  const curves = markets.map(({ data }) => get(data, 'walk_forward.equity_curve', []))
  const shared = extent(curves.flat())
  return (
    <section>
      <h2>Walk-forward results</h2>
      <p>
        {markets.map(({ label, data }) => `${label}: alpha ${sigText(wf(data).alpha_significant)}.`).join(' ')} Returns are cumulative over the test window, after the stated costs.
      </p>
      <div className="wf">
        <Table
          columns={[
            { key: 'metric', label: 'Metric' },
            { key: 'us', label: 'US', num: true },
            { key: 'india', label: 'India', num: true },
          ]}
          rows={rows}
        />
      </div>
      <div className="cols">
        {markets.map(({ label, data }, i) => (
          <Chart
            key={label}
            title={`${label} walk-forward`}
            rows={curves[i]}
            labels={['Portfolio', get(data, 'benchmark.label', 'Benchmark')]}
            yLabel="Start = 100, shared scale"
            domain={shared}
            compact
          />
        ))}
      </div>
    </section>
  )
}

function Weights() {
  return (
    <section>
      <h2>Current portfolio weights</h2>
      <div className="cols">
        {markets.map(({ label, data }) => (
          <Table
            key={label}
            caption={`${label}, ${get(data, 'generated', 'n/a')}, regime ${regimeText(data)}`}
            columns={[
              { key: 'ticker', label: 'Ticker' },
              { key: 'weight_pct', label: 'Weight', num: true, render: (r) => pct(r.weight_pct) },
              { key: 'composite', label: 'Composite', num: true, render: (r) => num(r.composite, 2) },
            ]}
            rows={get(data, 'weights', [])}
          />
        ))}
      </div>
    </section>
  )
}

function Ledger() {
  return (
    <section>
      <h2>Signal ledger</h2>
      <p className="muted">Every signal tested, with the statistic that decided it.</p>
      <Table
        columns={[
          { key: 'name', label: 'Signal' },
          { key: 'market', label: 'Market' },
          { key: 'category', label: 'Category' },
          { key: 'key_statistic', label: 'Key statistic' },
          { key: 'verdict', label: 'Verdict', tone: (r) => (r.verdict === 'rejected' ? 'neg' : r.verdict === 'approved' ? 'pos' : '') },
        ]}
        rows={ledger}
      />
    </section>
  )
}

function Orb() {
  const ratio = (v) => (isNum(v) && isNum(orb.notional) && orb.notional !== 0 ? pct((v / orb.notional) * 100) : 'n/a')
  return (
    <section>
      <h2>Intraday ORB study</h2>
      <p>
        Opening range breakout on NIFTYBEES, rules frozen and registered {dateOnly(orb.registered)} before data collection. {num(orb.sessions, 0)} sessions, {num(orb.triggered, 0)} triggered, {num(orb.wins, 0)} wins.
      </p>
      <StatRow
        items={[
          { label: 'Win rate', value: pct(orb.win_rate_pct) },
          { label: 'Breakeven win rate', value: pct(orb.breakeven_win_rate_pct) },
          { label: 'Gross, % of notional', value: ratio(orb.gross) },
          { label: 'Costs, % of notional', value: ratio(orb.costs) },
          { label: 'Net, % of notional', value: ratio(orb.net), tone: tone(orb.net) },
          { label: 'Max drawdown, % of notional', value: ratio(orb.max_drawdown) },
          { label: 'Bootstrap P(mean <= 0)', value: pval(orb.bootstrap_p) },
        ]}
      />
      <p>Verdict: {verdict()}.</p>
      <p className="muted">{text(orb.benchmark_note)}</p>
    </section>
  )
}

function Footer({ asOf }) {
  const boot = get(us, 'walk_forward.bootstrap_ci', {})
  return (
    <footer>
      <p>
        Method: expanding-window walk-forward, minimum {num(get(us, 'walk_forward.min_train_days'), 0)} training days, {num(get(us, 'walk_forward.step_days'), 0)}-day steps.
        Bootstrap: {num(boot.n_bootstrap, 0)} resamples, {isNum(boot.ci_level) ? pct(boot.ci_level * 100, 0) : 'n/a'} intervals. Deflated Sharpe: {num(get(us, 'deflated_sharpe.n_trials'), 0)} trials.
        Costs: US {text(get(us, 'walk_forward.cost_model'))}; India {text(get(india, 'walk_forward.cost_model'))}.
      </p>
      <p>Data as of {asOf}. Personal research project, not investment advice.</p>
    </footer>
  )
}

export default function App() {
  const live = useLive()
  const asOf = [get(us, 'generated'), get(india, 'generated'), dateOnly(get(live, 'generated'))].filter((d) => d && d !== 'n/a').sort().pop() || 'n/a'
  return (
    <main className="page">
      <Header asOf={asOf} />
      <Findings />
      <Live live={live} />
      <WalkForward />
      <Weights />
      <Ledger />
      <Orb />
      <Footer asOf={asOf} />
    </main>
  )
}
