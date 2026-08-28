export const isNum = (v) => typeof v === 'number' && Number.isFinite(v)

export const num = (v, d = 2) =>
  isNum(v) ? v.toLocaleString('en-US', { minimumFractionDigits: d, maximumFractionDigits: d }) : 'n/a'

export const pct = (v, d = 1, signed = false) =>
  isNum(v) ? `${signed && v > 0 ? '+' : ''}${v.toFixed(d)}%` : 'n/a'

export const pval = (p) => (isNum(p) ? (p < 0.001 ? '< 0.001' : p.toFixed(3)) : 'n/a')

export const pText = (p) => (isNum(p) ? (p < 0.001 ? 'p < 0.001' : `p = ${p.toFixed(3)}`) : 'p n/a')

export const ci = (arr, d = 1) =>
  Array.isArray(arr) && arr.length === 2 && arr.every(isNum) ? `[${arr[0].toFixed(d)}, ${arr[1].toFixed(d)}]` : 'n/a'

export const yesNo = (v) => (v === true ? 'yes' : v === false ? 'no' : 'n/a')

export const tone = (v) => (isNum(v) && v !== 0 ? (v > 0 ? 'pos' : 'neg') : '')

export const text = (v) => (v === null || v === undefined || v === '' ? 'n/a' : String(v))

export const dateOnly = (v) => (typeof v === 'string' && v.length >= 10 ? v.slice(0, 10) : 'n/a')

export function get(obj, path, fallback) {
  const v = path.split('.').reduce((o, k) => (o !== null && o !== undefined ? o[k] : undefined), obj)
  return v === undefined || v === null ? fallback : v
}
