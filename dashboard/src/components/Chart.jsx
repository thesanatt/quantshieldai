import { useId, useMemo, useState } from 'react'
import Table from './Table'
import { isNum, num } from '../fmt'

const H = 240
const PAD = { top: 12, right: 14, bottom: 26, left: 48 }
const PH = H - PAD.top - PAD.bottom
const TIP_W = 156
const STEPS = [0.01, 0.02, 0.05, 0.1, 0.2, 0.5, 1, 2, 5, 10, 20, 50, 100, 200, 500, 1000, 2000, 5000]
const TIP_H = 54
const SERIES = [
  { key: 'portfolio', cls: 'c-port' },
  { key: 'benchmark', cls: 'c-bench' },
]

export function sampleRows(rows, max = 400) {
  if (!Array.isArray(rows)) return []
  if (rows.length <= max) return rows
  const step = (rows.length - 1) / (max - 1)
  return Array.from({ length: max }, (_, i) => rows[Math.round(i * step)])
}

export function extent(rows) {
  const vals = sampleRows(rows).flatMap((r) => SERIES.map((s) => r[s.key]).filter(isNum))
  return vals.length ? [Math.min(...vals), Math.max(...vals)] : [0, 1]
}

function scaleFor([min, max], count = 4) {
  const span = max - min || 1
  const lo = min - span * 0.05
  const hi = max + span * 0.05
  const step = STEPS.find((s) => span / s <= count) || STEPS[STEPS.length - 1]
  const ticks = []
  for (let v = Math.ceil(lo / step) * step; v <= hi; v += step) ticks.push(Number(v.toFixed(6)))
  return { lo, hi, ticks, decimals: step < 0.1 ? 2 : step < 1 ? 1 : 0 }
}

function dateLabel(d, long) {
  return typeof d === 'string' ? d.slice(0, long ? 10 : 7) : ''
}

export default function Chart({ title, rows, labels, yLabel, domain, compact = false }) {
  const id = useId()
  const [showTable, setShowTable] = useState(false)
  const [idx, setIdx] = useState(null)
  const data = useMemo(() => sampleRows(rows), [rows])
  const n = data.length
  const W = compact ? 420 : 640
  const PW = W - PAD.left - PAD.right
  const { lo, hi, ticks, decimals } = useMemo(() => scaleFor(domain || extent(data)), [data, domain])
  const x = (i) => PAD.left + (n > 1 ? (i / (n - 1)) * PW : PW / 2)
  const y = (v) => PAD.top + PH - ((v - lo) / (hi - lo || 1)) * PH
  const first = data[0]?.date
  const last = data[n - 1]?.date
  const spanDays = (Date.parse(last) - Date.parse(first)) / 86400000
  const longDates = !Number.isFinite(spanDays) || spanDays <= 400
  const xTicks = n > 1 ? [...new Set([0, Math.round((n - 1) / 3), Math.round((2 * (n - 1)) / 3), n - 1])] : [0]

  const pathFor = (key) => {
    let d = ''
    data.forEach((r, i) => {
      if (isNum(r[key])) d += `${d ? 'L' : 'M'}${x(i).toFixed(1)},${y(r[key]).toFixed(1)}`
    })
    return d
  }

  const onMove = (e) => {
    const rect = e.currentTarget.getBoundingClientRect()
    const px = ((e.clientX - rect.left) / rect.width) * W
    const t = Math.min(1, Math.max(0, (px - PAD.left) / PW))
    setIdx(Math.round(t * (n - 1)))
  }

  const onKey = (e) => {
    const cur = idx ?? n - 1
    const next = { ArrowLeft: cur - 1, ArrowRight: cur + 1, Home: 0, End: n - 1 }[e.key]
    if (next === undefined) return
    e.preventDefault()
    setIdx(Math.min(n - 1, Math.max(0, next)))
  }

  const columns = [
    { key: 'date', label: 'Date' },
    { key: 'portfolio', label: labels[0], num: true, render: (r) => num(r.portfolio, 2) },
    { key: 'benchmark', label: labels[1], num: true, render: (r) => num(r.benchmark, 2) },
  ]

  const point = idx !== null && n > 0 ? data[idx] : null
  const readout = point
    ? `${point.date}: ${labels[0]} ${num(point.portfolio, 2)}, ${labels[1]} ${num(point.benchmark, 2)}`
    : ''
  const tipX = point ? (x(idx) > W / 2 ? x(idx) - 10 - TIP_W : x(idx) + 10) : 0

  return (
    <div className="chart">
      <div className="chart-head">
        <h3>{title}</h3>
        <button type="button" aria-pressed={showTable} onClick={() => setShowTable((v) => !v)}>
          {showTable ? 'Chart' : 'Table'}
        </button>
      </div>
      <div className="legend">
        {SERIES.map((s, i) => (
          <span key={s.key}>
            <span className={`swatch ${s.cls}`} />
            {labels[i]}
          </span>
        ))}
        <span className="muted">{yLabel}</span>
      </div>
      {showTable && <Table scroll caption={`${title}, ${n} of ${rows?.length ?? 0} rows`} columns={columns} rows={data} />}
      {!showTable && n === 0 && <p className="muted">n/a</p>}
      {!showTable && n > 0 && (
        <div
          className="plot"
          tabIndex={0}
          role="img"
          aria-label={`${title}: ${labels[0]} and ${labels[1]} from ${first} to ${last}. Arrow keys move the readout.`}
          aria-describedby={id}
          onKeyDown={onKey}
          onFocus={() => setIdx((v) => v ?? n - 1)}
          onBlur={() => setIdx(null)}
        >
          <svg viewBox={`0 0 ${W} ${H}`} onPointerMove={onMove} onPointerLeave={() => setIdx(null)}>
            {ticks.map((t) => (
              <g key={t}>
                <line className="axis" x1={PAD.left} x2={W - PAD.right} y1={y(t)} y2={y(t)} />
                <text className="tick" x={PAD.left - 8} y={y(t) + 4} textAnchor="end">
                  {num(t, decimals)}
                </text>
              </g>
            ))}
            <line className="axis" x1={PAD.left} x2={PAD.left} y1={PAD.top} y2={PAD.top + PH} />
            <line className="axis" x1={PAD.left} x2={W - PAD.right} y1={PAD.top + PH} y2={PAD.top + PH} />
            {xTicks.map((i, k) => (
              <text
                key={i}
                className="tick"
                x={x(i)}
                y={H - 8}
                textAnchor={k === 0 ? 'start' : k === xTicks.length - 1 ? 'end' : 'middle'}
              >
                {dateLabel(data[i].date, longDates)}
              </text>
            ))}
            {SERIES.map((s) => (
              <path key={s.key} className={`series ${s.cls}`} d={pathFor(s.key)} />
            ))}
            {point && (
              <g>
                <line className="crosshair" x1={x(idx)} x2={x(idx)} y1={PAD.top} y2={PAD.top + PH} />
                {SERIES.map(
                  (s) => isNum(point[s.key]) && <circle key={s.key} className={`dot ${s.cls}`} cx={x(idx)} cy={y(point[s.key])} r={4} />,
                )}
                <rect className="tip-box" x={tipX} y={PAD.top} width={TIP_W} height={TIP_H} rx={2} />
                <text className="tip-text" x={tipX + 8} y={PAD.top + 16}>
                  {point.date}
                </text>
                <text className="tip-text" x={tipX + 8} y={PAD.top + 31}>
                  {labels[0]} {num(point.portfolio, 2)}
                </text>
                <text className="tip-text" x={tipX + 8} y={PAD.top + 46}>
                  {labels[1]} {num(point.benchmark, 2)}
                </text>
              </g>
            )}
          </svg>
        </div>
      )}
      <div id={id} className="sr-only" aria-live="polite">
        {readout}
      </div>
    </div>
  )
}
