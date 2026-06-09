import { escapeHtml } from './api.js'

export function getType(value) {
  if (value === null) return 'null'
  if (Array.isArray(value)) return 'array'
  return typeof value
}

export function renderMarkdown(text) {
  if (text == null) return ''
  let html = String(text)

  html = html.replace(/&/g, '&amp;')
  html = html.replace(/</g, '&lt;')
  html = html.replace(/>/g, '&gt;')

  html = html.replace(/```([\s\S]*?)```/g, (_, code) => {
    return `<pre><code>${code}</code></pre>`
  })

  html = html.replace(/^### (.+)$/gm, '<h3>$1</h3>')
  html = html.replace(/^## (.+)$/gm, '<h2>$1</h2>')
  html = html.replace(/^# (.+)$/gm, '<h1>$1</h1>')

  html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
  html = html.replace(/(^|[^*])\*([^*]+)\*/g, '$1<em>$2</em>')
  html = html.replace(/`([^`]+)`/g, '<code>$1</code>')

  html = html.replace(/\[\[([^\]|]+)\|([^\]]+)\]\]/g,
    '<a href="#" data-wiki-link="$1" class="wiki-link">$2</a>')
  html = html.replace(/\[\[([^\]]+)\]\]/g,
    '<a href="#" data-wiki-link="$1" class="wiki-link">$1</a>')
  html = html.replace(/\[([^\]]+)\]\(([^)]+)\)/g,
    '<a href="#" data-wiki-link="$2" class="wiki-link">$1</a>')

  html = html.replace(/^&gt; (.+)$/gm, '<blockquote>$1</blockquote>')

  html = html.replace(/^\|(.+)\|$/gm, (match) => {
    const cells = match.split('|').filter(c => c.trim())
    if (cells.every(c => /^[\s\-:]+$/.test(c))) return '<!--table-sep-->'
    const row = cells.map(c => `<td>${c.trim()}</td>`).join('')
    return `<tr>${row}</tr>`
  })
  html = html.replace(/((?:<tr>.*<\/tr>\n?)+)/g, (match) => {
    let table = match.replace('<!--table-sep-->\n', '').replace('<!--table-sep-->', '')
    table = table.replace(/<tr>(.*?)<\/tr>/, (m, inner) =>
      '<thead><tr>' + inner.replace(/<td>/g, '<th>').replace(/<\/td>/g, '</th>') + '</tr></thead><tbody>')
    table += '</tbody>'
    return `<table>${table}</table>`
  })

  html = html.replace(/^- (.+)$/gm, '<li>$1</li>')
  html = html.replace(/((?:<li>.*<\/li>\n?)+)/g, '<ul>$1</ul>')

  html = html.replace(/^---$/gm, '<hr>')

  const paragraphs = html.split(/\n\n+/)
  html = paragraphs.map(p => {
    if (/^\s*<(h[1-3]|ul|ol|pre|blockquote|table|hr)/.test(p)) return p
    if (p.trim() === '') return ''
    return `<p>${p.replace(/\n/g, '<br>')}</p>`
  }).join('\n')

  return html
}
