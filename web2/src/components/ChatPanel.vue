<template>
  <button v-if="visible" class="chat-toggle" @click="toggle">
    <span v-html="I.chat" style="width:22px;height:22px"></span>
  </button>

  <div v-if="visible" class="chat-panel" :class="{ open: panelOpen }">
    <div class="chat-header">
      <div>
        <div class="uppercase-label" style="color:var(--neon-cyan)">Assistant</div>
        <div class="chat-header-title">{{ projectName || 'Knowledge Assistant' }}</div>
      </div>
      <button class="btn btn-sm btn-ghost" @click="toggle">
        <span v-html="I.x" style="width:14px;height:14px"></span>
      </button>
    </div>

    <div class="chat-messages" ref="messagesRef">
      <div v-if="messages.length === 0" style="text-align:center;padding:30px 10px">
        <span v-html="I.bolt" style="width:40px;height:40px;color:var(--neon-cyan)"></span>
        <p style="margin:10px 0;color:var(--text-muted);font-size:13px">Ask anything about the project, concepts, or files.</p>
      </div>

      <div v-for="(m, i) in messages" :key="i" class="chat-message" :class="m.role">
        <div class="chat-bubble">{{ m.content }}</div>
      </div>

      <div v-if="loading" class="chat-message assistant">
          <div class="chat-bubble" style="opacity:0.7">
            <span class="loading-dots"><span></span><span></span><span></span></span>
          </div>
      </div>
    </div>

    <div class="chat-input-area">
      <textarea v-model="input" @keydown.enter.prevent="send" placeholder="Ask the knowledge base..." :disabled="loading"></textarea>
      <button class="chat-send-btn" @click="send" :disabled="!input.trim() || loading">
        <span v-html="I.send" style="width:16px;height:16px"></span>
      </button>
    </div>
  </div>
</template>

<script setup>
import { ref, nextTick, watch } from 'vue'
import { I } from '../utils/icons.js'

const props = defineProps({
  visible: { type: Boolean, default: false },
  projectName: { type: String, default: '' }
})
const emit = defineEmits(['send'])

const panelOpen = ref(false)
const input = ref('')
const messages = ref([])
const loading = ref(false)
const messagesRef = ref(null)

function toggle() {
  panelOpen.value = !panelOpen.value
}
async function send() {
  const text = input.value.trim()
  if (!text || loading.value) return
  messages.value.push({ role: 'user', content: text })
  input.value = ''
  loading.value = true
  await nextTick()
  scrollToBottom()
  // Delegate to parent if connected
  emit('send', { text, onResponse })
}
function onResponse(content) {
  messages.value.push({ role: 'assistant', content })
  loading.value = false
  nextTick(scrollToBottom)
}
function scrollToBottom() {
  if (messagesRef.value) {
    messagesRef.value.scrollTop = messagesRef.value.scrollHeight
  }
}
watch(loading, scrollToBottom)
</script>
