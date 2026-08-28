export function Stat({ label, value, tone = '' }) {
  return (
    <div className="stat">
      <div className="stat-label">{label}</div>
      <div className={`stat-value ${tone}`.trim()}>{value}</div>
    </div>
  )
}

export function StatRow({ items }) {
  return (
    <div className="stats">
      {items.map((item) => (
        <Stat key={item.label} {...item} />
      ))}
    </div>
  )
}
