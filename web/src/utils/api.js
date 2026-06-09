const API_BASE = ''

export async function api(path, options = {}) {
  const url = `${API_BASE}/api${path}`
  const res = await fetch(url, {
    headers: { 'Content-Type': 'application/json' },
    ...options
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: res.statusText }))
    throw new Error(err.error || `HTTP ${res.status}`)
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
  return str.replace(/"/g, '&quot;').replace(/'/g, '&#39;')
}

export function unescapeHtml(str) {
  const div = document.createElement('div')
  div.innerHTML = str
  return div.textContent
}

export function getFileType(path) {
  if (path.startsWith('raw/')) return 'raw'
  if (path.startsWith('wiki/sources/')) return 'source'
  if (path.startsWith('wiki/concepts/')) return 'concept'
  if (path.startsWith('wiki/entities/')) return 'entity'
  if (path.startsWith('wiki/')) return 'wiki'
  if (path.startsWith('graph/')) return 'graph'
  return 'other'
}

export const fileTypeColors = {
  source: '#86E8B8',
  entity: '#3EB8FF',
  concept: '#FFD648',
  synthesis: '#E96FC2'
}
