<template>
  <aside class="chat-dock" :class="{ open }">
    <div v-show="open" class="chat-panel glass-strong">
      <!-- Header -->
      <div class="chat-header">
        <div class="chat-header-left">
          <div class="chat-ai-icon">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
              <circle cx="12" cy="12" r="3" />
              <path d="M12 1v4m0 14v4M4.22 4.22l2.83 2.83m9.9 9.9l2.83 2.83" />
            </svg>
          </div>
          <div>
            <h3>Knowledge Base Q&A</h3>
            <span class="chat-subtitle">AI-powered answers</span>
          </div>
        </div>
        <button class="chat-close" @click="closePanel" title="Close chat">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
          </svg>
        </button>
      </div>

      <!-- Messages -->
      <div class="chat-messages" ref="messagesRef" @click="onMessageClick">
        <div v-if="messages.length === 0" class="chat-welcome">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
            <circle cx="12" cy="12" r="3" />
            <path d="M12 1v4m0 14v4M4.22 4.22l2.83 2.83m9.9 9.9l2.83 2.83M1 12h4m14 0h4" />
          </svg>
          <p>Ask questions about your knowledge base.<br/>AI will answer based on the content.</p>
        </div>

        <div v-for="(msg, i) in messages" :key="i" class="chat-message" :class="msg.role">
          <div class="chat-avatar">{{ msg.role === 'user' ? 'U' : '' }}
            <svg v-if="msg.role === 'assistant'" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <circle cx="12" cy="12" r="3" />
              <path d="M12 1v4m0 14v4M4.22 4.22l2.83 2.83m9.9 9.9l2.83 2.83" />
            </svg>
          </div>
          <div class="chat-bubble">
            <template v-if="msg.role === 'assistant'">
              <span v-html="rendered(msg.content)"></span>
            </template>
            <template v-else>{{ msg.content }}</template>
          </div>
        </div>

        <div v-if="isTyping" class="chat-message assistant chat-typing">
          <div class="chat-avatar">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <circle cx="12" cy="12" r="3" />
            </svg>
          </div>
          <div class="chat-bubble typing-dots">
            <span></span><span></span><span></span>
          </div>
        </div>
      </div>

      <!-- Input Area -->
      <div class="chat-input-area glass-subtle">
        <textarea
          ref="inputRef"
          v-model="inputText"
          placeholder="Ask a question, press Enter to send..."
          rows="1"
          @keydown="onKeyDown"
          @input="autoResize"
        ></textarea>
        <button class="chat-send-btn" :disabled="isTyping || !inputText.trim()" @click="sendMessage">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <line x1="22" y1="2" x2="11" y2="13" />
            <polygon points="22 2 15 22 11 13 2 9 22 2" />
          </svg>
        </button>
      </div>
    </div>
  </aside>
</template>

<script setup>
import { ref, watch, nextTick } from 'vue'
import { renderMarkdown } from '../utils/markdown.js'

const props = defineProps({
  open: { type: Boolean, default: false },
  currentKbId: { type: [String, Number], default: null },
  queryApi: { type: Function, required: true },
  openWikiLink: { type: Function, default: null }
})

const emit = defineEmits(['update:open'])

const inputText = ref('')
const messages = ref([])
const isTyping = ref(false)
const messagesRef = ref(null)
const inputRef = ref(null)

function rendered(text) {
  return renderMarkdown(text)
}

function closePanel() {
  emit('update:open', false)
}

watch(
  () => props.open,
  (val) => {
    if (val) {
      nextTick(() => inputRef.value?.focus())
    }
  }
)

watch(
  () => props.currentKbId,
  () => {
    messages.value = []
    inputText.value = ''
    isTyping.value = false
    console.log('[ChatPanel] cleared messages on kb change')
  }
)

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

function onMessageClick(e) {
  const link = e.target.closest('a.wiki-link')
  if (link && props.openWikiLink) {
    e.preventDefault()
    const target = link.getAttribute('data-wiki-link') || link.textContent
    props.openWikiLink(target)
  }
}

async function sendMessage() {
  const text = inputText.value.trim()
  if (!text || isTyping.value) return
  if (!props.currentKbId) {
    alert('Please select a kb first')
    return
  }

  console.log('[ChatPanel] send', { questionLen: text.length, kbId: props.currentKbId })
  messages.value.push({ role: 'user', content: text })
  inputText.value = ''
  autoResize()
  isTyping.value = true

  nextTick(() => {
    if (messagesRef.value) {
      messagesRef.value.scrollTop = messagesRef.value.scrollHeight
    }
  })

  let assistantMsg = null

  try {
    await props.queryApi(text, (chunk) => {
      if (!assistantMsg) {
        isTyping.value = false
        messages.value.push({ role: 'assistant', content: chunk })
        assistantMsg = messages.value[messages.value.length - 1]
      } else {
        assistantMsg.content += chunk
      }
      nextTick(() => {
        if (messagesRef.value) {
          messagesRef.value.scrollTop = messagesRef.value.scrollHeight
        }
      })
    })

    if (!assistantMsg) {
      isTyping.value = false
      messages.value.push({ role: 'assistant', content: 'No response received.' })
    }
    console.log('[ChatPanel] reply ok')
  } catch (err) {
    console.error('[ChatPanel] reply failed', err.message)
    isTyping.value = false
    if (assistantMsg) {
      assistantMsg.content += `\n\n*Error: ${err.message}*`
    } else {
      messages.value.push({ role: 'assistant', content: `Error: ${err.message}` })
    }
  }
}
</script>

<style scoped>
.chat-dock {
  width: 0;
  flex-shrink: 0;
  overflow: hidden;
  transition: width 200ms ease;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.chat-dock.open {
  width: 380px;
}

.chat-panel {
  width: 380px;
  height: 100%;
  border-radius: var(--radius-xl);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  min-height: 0;
}

.chat-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 18px;
  border-bottom: 1px solid rgba(0, 0, 0, 0.06);
  flex-shrink: 0;
}

.chat-header-left {
  display: flex;
  align-items: center;
  gap: 10px;
}

.chat-ai-icon {
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, var(--accent), var(--accent-purple));
  border-radius: 10px;
  color: #fff;
}

.chat-ai-icon svg {
  width: 16px;
  height: 16px;
}

.chat-header h3 {
  font-size: 0.875rem;
  font-weight: 600;
  color: var(--text-primary);
  letter-spacing: -0.01em;
}

.chat-subtitle {
  font-size: 0.6875rem;
  color: var(--text-tertiary);
}

.chat-close {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border-radius: 50%;
  border: none;
  background: rgba(0, 0, 0, 0.04);
  color: var(--text-secondary);
  cursor: pointer;
  transition: all var(--transition-fast);
}

.chat-close:hover {
  background: rgba(0, 0, 0, 0.08);
  color: var(--text-primary);
}

.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 16px;
  min-height: 0;
}

.chat-welcome {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  padding: 40px 20px;
  text-align: center;
  color: var(--text-tertiary);
}

.chat-welcome svg {
  width: 36px;
  height: 36px;
  opacity: 0.3;
}

.chat-welcome p {
  font-size: 0.8125rem;
  line-height: 1.6;
}

.chat-message {
  display: flex;
  gap: 10px;
  animation: fadeInUp 300ms var(--ease-out-expo);
}

.chat-avatar {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 0.6875rem;
  font-weight: 600;
  flex-shrink: 0;
  color: #fff;
  overflow: hidden;
}

.chat-message.user .chat-avatar {
  background: var(--accent);
}

.chat-message.assistant .chat-avatar {
  background: linear-gradient(135deg, var(--accent-purple), var(--accent));
}

.chat-avatar svg {
  width: 14px;
  height: 14px;
}

.chat-bubble {
  padding: 10px 14px;
  border-radius: var(--radius-sm);
  font-size: 0.8125rem;
  line-height: 1.6;
  max-width: 85%;
}

.chat-message.user {
  flex-direction: row-reverse;
}

.chat-message.user .chat-bubble {
  background: var(--accent);
  color: #fff;
  border-bottom-right-radius: 4px;
}

.chat-message.assistant .chat-bubble {
  background: rgba(0, 0, 0, 0.04);
  color: var(--text-primary);
  border-bottom-left-radius: 4px;
}

.chat-message.assistant .chat-bubble :deep(p) {
  margin: 4px 0;
}

.chat-message.assistant .chat-bubble :deep(code) {
  font-family: var(--font-mono);
  font-size: 0.75rem;
  background: rgba(0, 0, 0, 0.06);
  padding: 1px 4px;
  border-radius: 3px;
}

.chat-message.assistant .chat-bubble :deep(pre) {
  background: rgba(0, 0, 0, 0.04);
  padding: 10px;
  border-radius: 6px;
  overflow-x: auto;
  margin: 6px 0;
}

.typing-dots {
  display: flex;
  gap: 4px;
  padding: 14px 18px;
}

.typing-dots span {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--text-tertiary);
  animation: typingBounce 1.4s infinite ease-in-out;
}

.typing-dots span:nth-child(1) { animation-delay: 0s; }
.typing-dots span:nth-child(2) { animation-delay: 0.2s; }
.typing-dots span:nth-child(3) { animation-delay: 0.4s; }

@keyframes typingBounce {
  0%, 80%, 100% { transform: scale(0.6); opacity: 0.4; }
  40% { transform: scale(1); opacity: 1; }
}

.chat-input-area {
  display: flex;
  align-items: flex-end;
  gap: 8px;
  padding: 12px 14px;
  border-top: 1px solid rgba(0, 0, 0, 0.06);
  flex-shrink: 0;
}

.chat-input-area textarea {
  flex: 1;
  resize: none;
  font-size: 0.8125rem;
  line-height: 1.5;
  background: transparent;
  border: none;
  outline: none;
  color: var(--text-primary);
  font-family: var(--font-sans);
  padding: 4px 0;
}

.chat-input-area textarea::placeholder {
  color: var(--text-placeholder);
}

.chat-send-btn {
  width: 34px;
  height: 34px;
  border-radius: 50%;
  border: none;
  background: var(--accent);
  color: #fff;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  transition: all var(--transition-fast);
}

.chat-send-btn:hover:not(:disabled) {
  background: #0070E9;
  transform: scale(1.05);
}

.chat-send-btn:disabled {
  opacity: 0.3;
  cursor: not-allowed;
}

.chat-send-btn svg {
  width: 14px;
  height: 14px;
}
</style>
