import { text } from '../fmt'

export default function Table({ caption, columns, rows, scroll = false }) {
  const list = Array.isArray(rows) ? rows : []
  return (
    <div className={scroll ? 'table-wrap scroll' : 'table-wrap'}>
      <table>
        {caption && <caption>{caption}</caption>}
        <thead>
          <tr>
            {columns.map((c) => (
              <th key={c.key} className={c.num ? 'num' : undefined}>
                {c.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {list.length === 0 && (
            <tr>
              <td colSpan={columns.length}>n/a</td>
            </tr>
          )}
          {list.map((row, i) => (
            <tr key={row.key ?? i}>
              {columns.map((c) => (
                <td key={c.key} className={[c.num ? 'num' : '', c.tone ? c.tone(row) : ''].join(' ').trim() || undefined}>
                  {c.render ? c.render(row) : text(row[c.key])}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
