export function clampNumber(v) {
  const n = Number(v)
  if (!Number.isFinite(n)) return 0
  return n
}

export function formatNumber(v) {
  const n = Number(v)
  if (!Number.isFinite(n)) return '0'
  return new Intl.NumberFormat('vi-VN', { maximumFractionDigits: 2 }).format(n)
}

export function shortUrl(url) {
  if (!url) return ''
  try {
    const u = new URL(url)
    return `${u.hostname}${u.pathname}`
  } catch {
    return url.length > 48 ? `${url.slice(0, 45)}...` : url
  }
}

export function groupBy(arr, keyFn) {
  const out = new Map()
  for (const it of arr) {
    const k = keyFn(it)
    if (!out.has(k)) out.set(k, [])
    out.get(k).push(it)
  }
  return out
}

