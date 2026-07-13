/**
 * 消费 SSE (Server-Sent Events) 响应流。
 * @param {string} url - 请求 URL
 * @param {RequestInit} options - fetch 选项
 * @param {(event: object) => void} [onEvent] - 每个 SSE 事件的回调
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

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })

    const lines = buffer.split('\n')
    buffer = lines.pop() || ''
    for (const line of lines) {
      if (!line.startsWith('data: ')) continue
      try {
        const data = JSON.parse(line.slice(6))
        if (data.event === 'error') {
          throw new Error(data.message || 'Stream error')
        }
        if (data.event === 'done') {
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
 * @param {string} url - 请求 URL（可含 ?stream=true）
 * @param {FormData} formData - 表单数据
 * @param {(event: object) => void} [onEvent] - 每个 SSE 事件的回调
 * @returns {Promise<any>} done 事件中的 result
 */
export async function consumeSSEUpload(url, formData, onEvent) {
  console.log('[sse] POST upload', url)
  return consumeSSE(url, { method: 'POST', body: formData }, onEvent)
}
