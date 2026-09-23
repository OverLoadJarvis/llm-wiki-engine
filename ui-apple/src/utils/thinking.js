/**
 * Split assistant text into { content, thinking }.
 * Recognizes <think> and <thinking> (case-insensitive).
 * Merges all blocks; unclosed open tag → rest is thinking.
 */

const THINK_PAIR = /<(think|thinking)>([\s\S]*?)<\/\1>/gi
const THINK_OPEN = /<(think|thinking)>/i
const THINK_CLOSE = /<\/(?:think|thinking)>/gi

export function splitThinking(text) {
  if (!text) return { content: '', thinking: '' }

  const parts = []
  let content = String(text).replace(THINK_PAIR, (_m, _tag, inner) => {
    const chunk = (inner || '').trim()
    if (chunk) parts.push(chunk)
    return ''
  })

  const openM = content.match(THINK_OPEN)
  if (openM) {
    const idx = content.search(THINK_OPEN)
    const rest = content.slice(idx + openM[0].length).trim()
    if (rest) parts.push(rest)
    content = content.slice(0, idx)
  }

  content = content.replace(THINK_CLOSE, '').trim()
  const thinking = parts.join('\n\n')
  return { content, thinking }
}

export function stripThinking(text) {
  return splitThinking(text).content
}
