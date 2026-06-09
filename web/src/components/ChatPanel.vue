<template>
  <div>
    <button class="chat-toggle-btn" @click="togglePanel" title="与知识库对话">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
      </svg>
    </button>

    <div class="chat-panel" :class="{ hidden: !isOpen }">
      <div class="chat-header">
        <h3>💬 知识库问答</h3>
        <div class="chat-close" @click="togglePanel">&times;</div>
      </div>
      <div class="chat-messages" ref="messagesRef">
        <div v-if="messages.length === 0" class="chat-welcome">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
            <circle cx="12" cy="12" r="3"/>
            <path d="M12 1v4m0 14v4M4.22 4.22l2.83 2.83m9.9 9.9l2.83 2.83M1 12h4m14 0h4"/>
          </svg>
          <p>向知识库提问<br/>AI 将基于知识库内容回答</p>
        </div>

        <div v-for="(msg, i) in messages" :key="i" class="chat-message" :class="msg.role">
          <div class="chat-avatar">{{ msg.role === 'user' ? 'U' : 'AI' }}</div>
          <div class="chat-bubble">
            <template v-if="msg.role === 'assistant'"><span v-html="rendered(msg.content)"></span></template>
            <template v-else>{{ msg.content }}</template>
          </div>
        </div>

        <div v-if="isTyping" class="chat-message assistant chat-typing">
          <div class="chat-avatar">AI</div>
          <div class="chat-bubble">正在查询知识库...</div>
        </div>
      </div>

      <div class="chat-input-area">
        <textarea
          ref="inputRef"
          v-model="inputText"
          placeholder="输入问题，按 Enter 发送..."
          rows="1"
          @keydown="onKeyDown"
          @input="autoResize"
        ></textarea>
        <button class="chat-send-btn" :disabled="isTyping || !inputText.trim()" @click="sendMessage">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <line x1="22" y1="2" x2="11" y2="13"/>
            <polygon points="22 2 15 22 11 13 2 9 22 2"/>
          </svg>
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, nextTick, onMounted } from 'vue'
import { renderMarkdown } from '../utils/markdown.js'

const props = defineProps({
  currentProjectId: { type: [String, Number], default: null },
  queryApi: { type: Function, required: true }
})

const isOpen = ref(false)
const inputText = ref('')
const messages = ref([])
const isTyping = ref(false)
const messagesRef = ref(null)
const inputRef = ref(null)

function rendered(text) {
  return renderMarkdown(text)
}

function togglePanel() {
  if (!props.currentProjectId) {
    alert('请先选择项目')
    return
  }
  isOpen.value = !isOpen.value
  if (isOpen.value) {
    nextTick(() => inputRef.value?.focus())
  }
}

function onKeyDown(e) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    sendMessage()
  }
}

function autoResize() {
  const el = inputRef.value
  if (!el) return
  el.style.height = 'auto'
  el.style.height = Math.min(el.scrollHeight, 120) + 'px'
}

async function sendMessage() {
  const text = inputText.value.trim()
  if (!text || isTyping.value) return
  if (!props.currentProjectId) {
    alert('请先选择项目')
    return
  }

  messages.value.push({ role: 'user', content: text })
  inputText.value = ''
  isTyping.value = true
  nextTick(() => {
    const el = messagesRef.value
    if (el) el.scrollTop = el.scrollHeight
  })

  try {
    const result = await props.queryApi(text)
    messages.value.push({ role: 'assistant', content: result.answer })
  } catch (err) {
    messages.value.push({ role: 'assistant', content: `查询失败: ${err.message}` })
  } finally {
    isTyping.value = false
    nextTick(() => {
      const el = messagesRef.value
      if (el) el.scrollTop = el.scrollHeight
    })
  }
}

onMounted(() => {
  autoResize()
})
</script>
