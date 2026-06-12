import { escapeHtml } from './api.js'

export function renderMarkdown(text) {
  let html = text
  html = html.replace(/```(\w*)\n([\s\S]*?)```/g, '<pre><code>$2</code></pre>')
  html = html.replace(/^### (.+)$/gm, '<h3>$1</h3>')
  html = html.replace(/^## (.+)$/gm, '<h2>$1</h2>')
  html = html.replace(/^# (.+)$/gm, '<h1>$1</h1>')
  html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
  html = html.replace(/\*(.+?)\*/g, '<em>$1</em>')
  html = html.replace(/`([^`]+)`/g, '<code>$1</code>')
  html = html.replace(/\[\[([^\]|]+)\|([^\]]+)\]\]/g, '<a href="#" data-wiki-link="$1" class="wiki-link">$2</a>')
  html = html.replace(/\[\[([^\]]+)\]\]/g, '<a href="#" data-wiki-link="$1" class="wiki-link">$1</a>')
  html = html.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="#" data-wiki-link="$2" class="wiki-link">$1</a>')
  html = html.replace(/^> (.+)$/gm, '<blockquote>$1</blockquote>')
  html = html.replace(/^\|(.+)\|$/gm, (match) => {
    const cells = match.split('|').filter(c => c.trim())
    if (cells.every(c => /^[\s\-:]+$/.test(c))) return '<!--table-sep-->'
    const tag = 'td'
    const row = cells.map(c => `<${tag}>${c.trim()}</${tag}>`).join('')
    return `<tr>${row}</tr>`
  })
  html = html.replace(/((?:<tr>.*<\/tr>\n?)+)/g, (match) => {
    let table = match.replace('<!--table-sep-->\n', '').replace('<!--table-sep-->', '')
    table = table.replace(/<tr>(.*?)<\/tr>/, (m, inner) => `<thead><tr>${inner.replace(/<td>/g, '<th>').replace(/<\/td>/g, '</th>')}</tr></thead><tbody>`)
    table += '</tbody>'
    return `<table>${table}</table>`
  })
  html = html.replace(/^- (.+)$/gm, '<li>$1</li>')
  html = html.replace(/((?:<li>.*<\/li>\n?)+)/g, '<ul>$1</ul>')
  html = html.replace(/^---$/gm, '<hr>')
  html = html.replace(/\n\n/g, '</p><p>')
  html = '<p>' + html + '</p>'
  html = html.replace(/<p><(h[1-3]|ul|ol|pre|blockquote|table|hr)/g, '<$1')
  html = html.replace(/<\/(h[1-3]|ul|ol|pre|blockquote|table)><\/p>/g, '</$1>')
  html = html.replace(/<p><\/p>/g, '')
  html = html.replace(/<p><hr><\/p>/g, '<hr>')
  return html
}

export function renderJsonNode(value, path, isRoot = false) {
  const type = getType(value)
  const id = 'json-' + Math.random().toString(36).substr(2, 9)

  if (type === 'object' || type === 'array') {
    const isArray = type === 'array'
    const keys = Object.keys(value)
    const count = keys.length
    const openBracket = isArray ? '[' : '{'
    const closeBracket = isArray ? ']' : '}'

    let html = `
      <div class="json-node">
        <div class="json-toggle" data-toggle-id="${id}">
          <span class="json-arrow">▶</span>
          <span class="json-type">${isArray ? 'Array' : 'Object'}</span>
          <span class="json-count">(${count} ${count === 1 ? 'item' : 'items'})</span>
        </div>
        <div class="json-children" id="${id}">
          <span class="json-bracket">${openBracket}</span>
    `

    for (let i = 0; i < keys.length; i++) {
      const key = keys[i]
      const childValue = value[key]
      html += `
        <div class="json-item">
          <span class="json-key">${escapeHtml(isArray ? i : key)}:</span>
          ${renderJsonNode(childValue, '')}
          ${i < count - 1 ? '<span class="json-comma">,</span>' : ''}
        </div>
      `
    }

    html += `
          <span class="json-bracket">${closeBracket}</span>
        </div>
      </div>
    `
    return html
  } else {
    return `<span class="json-value json-${type}">${escapeHtml(String(value))}</span>`
  }
}

export function getType(value) {
  if (value === null) return 'null'
  if (Array.isArray(value)) return 'array'
  return typeof value
}
