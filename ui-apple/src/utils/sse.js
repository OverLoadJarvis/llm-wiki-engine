/**
 * 消费标准 SSE（event: + data:）响应流。
 * 回调收到的对象会带上 event 字段，兼容原 handleTaskEvent。
 * @param {string} url
 * @param {RequestInit} [options]
 * @param {(event: object) => void} [onEvent]
 * @returns {Promise<any>} done 事件中的 result，或 null
 */
export async function consumeSSE(url, options = {}, onEvent) {
  console.log('[sse] POST', url)
  const res = await fetch(url, options)
  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: res.statusText }))
    console.error('[sse] request failed', err.error || res.statusText)
    throw new Error(err.error || `HTTP ${res.status}`)
  }

  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  let finalResult = null
  let currentEvent = 'message'

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })

    const parts = buffer.split('\n')
    buffer = parts.pop() || ''
    for (const rawLine of parts) {
      const line = rawLine.replace(/\r$/, '')
      if (!line) {
        currentEvent = 'message'
        continue
      }
      if (line.startsWith('event:')) {
        currentEvent = line.slice(6).trim() || 'message'
        continue
      }
      if (!line.startsWith('data:')) continue
      const dataStr = line.slice(5).trim()
      try {
        const payload = dataStr ? JSON.parse(dataStr) : {}
        const data = { event: currentEvent, ...payload }
        if (currentEvent === 'error') {
          throw new Error(data.message || data.error || 'Stream error')
        }
        if (currentEvent === 'done') {
          finalResult = data.result ?? finalResult
        }
        if (onEvent) onEvent(data)
      } catch (e) {
        if (e instanceof SyntaxError) continue
        throw e
      }
    }
  }

  console.log('[sse] stream complete')
  return finalResult
}

/**
 * 消费 multipart 上传的 SSE 响应流。
 */
export async function consumeSSEUpload(url, formData, onEvent) {
  console.log('[sse] POST upload', url)
  return consumeSSE(url, { method: 'POST', body: formData }, onEvent)
}
