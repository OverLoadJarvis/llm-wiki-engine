const API_BASE = ''

export async function api(path, options = {}) {
  const url = `${API_BASE}/api${path}`
  const res = await fetch(url, {
    headers: { 'Content-Type': 'application/json' },
    ...options
  })
  if (!res.ok) {
    let msg = `HTTP ${res.status}`
    try {
      const err = await res.json()
      if (err && err.error) msg = err.error
    } catch (_) {}
    throw new Error(msg)
  }
  return res.json()
}

export async function apiText(path, options = {}) {
  const url = `${API_BASE}/api${path}`
  const res = await fetch(url, options)
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.text()
}

export function escapeHtml(str) {
  const div = document.createElement('div')
  div.textContent = str
  return div.innerHTML
}

export function escapeHtmlAttr(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}

export function getFileType(path) {
  if (!path) return 'other'
  if (path.startsWith('raw/')) return 'raw'
  if (path.startsWith('wiki/sources/')) return 'source'
  if (path.startsWith('wiki/concepts/')) return 'concept'
  if (path.startsWith('wiki/entities/')) return 'entity'
  if (path.startsWith('wiki/')) return 'wiki'
  if (path.startsWith('graph/')) return 'graph'
  return 'other'
}

export const fileTypeColors = {
  source: '#00F0FF',
  entity: '#FF2D95',
  concept: '#8A4BFF',
  synthesis: '#00FF88',
  default: '#6B7280'
}

export function formatNumber(n) {
  if (n == null) return '—'
  if (typeof n === 'number') return n.toLocaleString()
  return n
}

export function formatTimestamp(ts) {
  if (!ts) return '—'
  try {
    const d = new Date(ts)
    return d.toLocaleString()
  } catch (_) { return String(ts) }
}

export function debounce(fn, wait = 160) {
  let t = null
  return (...args) => {
    clearTimeout(t)
    t = setTimeout(() => fn(...args), wait)
  }
}
