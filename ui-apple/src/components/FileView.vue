<template>
  <div class="file-view">
    <!-- JSON Viewer -->
    <div class="file-content" v-if="fileType === 'json'">
      <div class="viewer-toolbar glass-subtle">
        <button class="btn btn-outline btn-sm" @click="toggleAllJson">
          {{ allExpanded ? 'Collapse All' : 'Expand All' }}
        </button>
        <button class="btn btn-outline btn-sm" @click="copyJson">Copy Raw</button>
      </div>
      <div class="viewer-body">
        <div v-if="jsonError" class="error-message">JSON parse error: {{ jsonError }}</div>
        <div v-else class="json-tree" v-html="jsonTreeHtml" @click="onJsonTreeClick"></div>
      </div>
    </div>

    <!-- HTML Viewer -->
    <div class="file-content" v-else-if="fileType === 'html'">
      <div class="viewer-toolbar glass-subtle">
        <button class="btn btn-outline btn-sm" :class="{ 'btn-active': htmlView === 'preview' }" @click="htmlView = 'preview'">Preview</button>
        <button class="btn btn-outline btn-sm" :class="{ 'btn-active': htmlView === 'source' }" @click="htmlView = 'source'">Source</button>
      </div>
      <div class="viewer-body">
        <div v-if="htmlView === 'preview'" class="html-preview">
          <iframe :srcdoc="content" sandbox="allow-scripts" class="html-iframe"></iframe>
        </div>
        <div v-else class="code-view">
          <pre><code>{{ content }}</code></pre>
        </div>
      </div>
    </div>

    <!-- Markdown Viewer -->
    <div class="file-content" v-else-if="fileType === 'md'">
      <div class="viewer-body md-body" v-html="renderedMarkdown" @click="onMarkdownClick"></div>
    </div>

    <!-- Plain Text Viewer -->
    <div class="file-content" v-else>
      <div class="viewer-toolbar glass-subtle">
        <span class="file-type-badge">.{{ ext }}</span>
        <button class="btn btn-outline btn-sm" @click="copyText">Copy</button>
      </div>
      <div class="viewer-body">
        <div class="code-view">
          <pre><code>{{ content }}</code></pre>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { escapeHtml } from '../utils/api.js'
import { renderMarkdown as mdRender } from '../utils/markdown.js'

const props = defineProps({
  filePath: { type: String, default: '' },
  content: { type: String, default: '' }
})

const emit = defineEmits(['open-link'])

const ext = computed(() => (props.filePath.split('.').pop() || '').toLowerCase())

const fileType = computed(() => {
  if (ext.value === 'json') return 'json'
  if (ext.value === 'html' || ext.value === 'htm') return 'html'
  if (ext.value === 'md' || ext.value === 'markdown') return 'md'
  return 'text'
})

const parsedJson = ref(null)
const jsonError = ref('')
const allExpanded = ref(true)
const htmlView = ref('preview')
const collapsedNodes = ref(new Set())

function parseJson() {
  if (!props.content || props.content.trim() === '') {
    jsonError.value = 'Empty file'
    parsedJson.value = null
    return
  }
  try {
    parsedJson.value = JSON.parse(props.content)
    jsonError.value = ''
  } catch (e) {
    jsonError.value = e.message
    parsedJson.value = null
  }
}

watch(() => props.content, () => {
  if (fileType.value === 'json') parseJson()
}, { immediate: true })

watch(allExpanded, (val) => {
  if (val) {
    collapsedNodes.value = new Set()
  }
})

const jsonTreeHtml = computed(() => {
  if (!parsedJson.value) return ''
  return renderJsonNode(parsedJson.value, 'root')
})

const renderedMarkdown = computed(() => mdRender(props.content))

function onMarkdownClick(e) {
  const link = e.target.closest('a.wiki-link')
  if (link) {
    e.preventDefault()
    const target = link.getAttribute('data-wiki-link') || link.textContent
    emit('open-link', target)
  }
}

function onJsonTreeClick(e) {
  const toggle = e.target.closest('.json-toggle')
  if (toggle) {
    const id = toggle.getAttribute('data-toggle-id')
    if (!id) return
    const children = document.getElementById(id)
    const arrow = toggle.querySelector('.json-arrow')
    if (children) {
      if (children.style.display === 'none') {
        children.style.display = ''
        if (arrow) arrow.style.transform = 'rotate(0deg)'
      } else {
        children.style.display = 'none'
        if (arrow) arrow.style.transform = 'rotate(-90deg)'
      }
    }
  }
}

function toggleAllJson() {
  allExpanded.value = !allExpanded.value
  const treeEl = document.querySelector('.json-tree')
  if (!treeEl) return
  const childrens = treeEl.querySelectorAll('.json-children')
  const arrows = treeEl.querySelectorAll('.json-arrow')
  if (allExpanded.value) {
    childrens.forEach(c => c.style.display = '')
    arrows.forEach(a => a.style.transform = 'rotate(0deg)')
  } else {
    childrens.forEach(c => c.style.display = 'none')
    arrows.forEach(a => a.style.transform = 'rotate(-90deg)')
  }
}

function copyJson() {
  navigator.clipboard.writeText(JSON.stringify(parsedJson.value, null, 2))
}

function copyText() {
  navigator.clipboard.writeText(props.content)
}

// ── JSON Renderer ─────────────────────────────────────────────
function getType(value) {
  if (value === null) return 'null'
  if (Array.isArray(value)) return 'array'
  return typeof value
}

let jsonNodeCounter = 0

function renderJsonNode(value, path) {
  const type = getType(value)
  const id = 'json-node-' + (jsonNodeCounter++)

  if (type === 'object' || type === 'array') {
    const isArray = type === 'array'
    const keys = Object.keys(value)
    const count = keys.length
    const openBracket = isArray ? '[' : '{'
    const closeBracket = isArray ? ']' : '}'

    if (count === 0) {
      return `<span class="json-bracket-inline">${openBracket}${closeBracket}</span>`
    }

    let html = `
      <div class="json-node">
        <div class="json-toggle" data-toggle-id="${id}">
          <span class="json-arrow">▼</span>
          <span class="json-type">${isArray ? 'Array' : 'Object'}</span>
          <span class="json-count">(${count} ${count === 1 ? 'item' : 'items'})</span>
          <span class="json-open-bracket">${openBracket}</span>
        </div>
        <div class="json-children" id="${id}">
    `

    for (let i = 0; i < keys.length; i++) {
      const key = keys[i]
      const childValue = value[key]
      const displayKey = isArray ? i : `"${escapeHtml(key)}"`
      html += `
        <div class="json-item">
          <span class="json-key">${displayKey}</span>
          <span class="json-colon">:</span>
          <span class="json-value-wrapper">${renderJsonNode(childValue, path + '/' + key)}</span>
          ${i < count - 1 ? '<span class="json-comma">,</span>' : ''}
        </div>
      `
    }

    html += `
          <span class="json-close-bracket">${closeBracket}</span>
        </div>
      </div>
    `
    return html
  } else {
    let display = escapeHtml(String(value))
    if (type === 'string') {
      display = `"${display}"`
    }
    return `<span class="json-value json-${type}">${display}</span>`
  }
}

onMounted(() => {
  jsonNodeCounter = 0
})
</script>

<style scoped>
.file-view {
  height: 100%;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.file-content {
  height: 100%;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.viewer-toolbar {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 16px;
  border-radius: var(--radius-sm);
  margin: 12px 16px 0;
  flex-shrink: 0;
}

.btn-active {
  background: rgba(0, 122, 255, 0.08);
  color: var(--accent);
  border-color: rgba(0, 122, 255, 0.2);
}

.viewer-body {
  flex: 1;
  overflow-y: auto;
  padding: 16px 24px;
}

/* ── Markdown Body ─────────────────────────────────────────── */
.md-body {
  line-height: 1.8;
  font-size: 0.9375rem;
  color: var(--text-primary);
  max-width: 860px;
  margin: 0 auto;
}

.md-body :deep(h1) {
  font-size: 1.75rem;
  font-weight: 700;
  letter-spacing: -0.03em;
  margin: 0 0 16px;
  padding-bottom: 12px;
  border-bottom: 1px solid rgba(0, 0, 0, 0.08);
}

.md-body :deep(h2) {
  font-size: 1.375rem;
  font-weight: 600;
  letter-spacing: -0.02em;
  margin: 32px 0 12px;
}

.md-body :deep(h3) {
  font-size: 1.125rem;
  font-weight: 600;
  letter-spacing: -0.01em;
  margin: 24px 0 8px;
}

.md-body :deep(p) {
  margin: 8px 0;
}

.md-body :deep(strong) {
  font-weight: 600;
}

.md-body :deep(code) {
  font-family: var(--font-mono);
  font-size: 0.8125rem;
  background: rgba(0, 0, 0, 0.04);
  padding: 2px 6px;
  border-radius: 4px;
}

.md-body :deep(pre) {
  background: rgba(0, 0, 0, 0.03);
  border: 1px solid rgba(0, 0, 0, 0.06);
  border-radius: var(--radius-sm);
  padding: 16px;
  overflow-x: auto;
  margin: 12px 0;
}

.md-body :deep(pre code) {
  background: none;
  padding: 0;
}

.md-body :deep(blockquote) {
  border-left: 3px solid var(--accent);
  padding: 4px 16px;
  margin: 12px 0;
  color: var(--text-secondary);
  background: rgba(0, 122, 255, 0.03);
  border-radius: 0 var(--radius-sm) var(--radius-sm) 0;
}

.md-body :deep(ul), .md-body :deep(ol) {
  padding-left: 24px;
  margin: 8px 0;
}

.md-body :deep(li) {
  margin: 4px 0;
}

.md-body :deep(a.wiki-link) {
  color: var(--accent);
  text-decoration: none;
  border-bottom: 1px solid rgba(0, 122, 255, 0.3);
  transition: border-color var(--transition-fast);
}

.md-body :deep(a.wiki-link:hover) {
  border-bottom-color: var(--accent);
}

.md-body :deep(table) {
  width: 100%;
  border-collapse: collapse;
  margin: 16px 0;
  font-size: 0.875rem;
}

.md-body :deep(th) {
  text-align: left;
  font-weight: 600;
  padding: 10px 14px;
  background: rgba(0, 0, 0, 0.03);
  border-bottom: 1px solid rgba(0, 0, 0, 0.08);
}

.md-body :deep(td) {
  padding: 10px 14px;
  border-bottom: 1px solid rgba(0, 0, 0, 0.04);
}

.md-body :deep(hr) {
  border: none;
  border-top: 1px solid rgba(0, 0, 0, 0.08);
  margin: 32px 0;
}

/* ── Code View ─────────────────────────────────────────────── */
.code-view {
  font-family: var(--font-mono);
  font-size: 0.8125rem;
  line-height: 1.7;
  color: var(--text-primary);
  background: rgba(0, 0, 0, 0.02);
  border-radius: var(--radius-md);
  padding: 20px;
  overflow: auto;
  height: 100%;
}

.code-view pre {
  white-space: pre-wrap;
  word-break: break-word;
}

/* ── HTML Preview ──────────────────────────────────────────── */
.html-preview {
  height: 100%;
  border-radius: var(--radius-md);
  overflow: hidden;
}

.html-iframe {
  width: 100%;
  height: 100%;
  border: none;
  background: #fff;
}

/* ── JSON Tree ─────────────────────────────────────────────── */
.json-tree {
  font-family: var(--font-mono);
  font-size: 0.8125rem;
  line-height: 1.8;
  padding: 16px 20px;
  background: rgba(0, 0, 0, 0.02);
  border-radius: var(--radius-md);
  min-height: 100%;
}

.json-tree :deep(.json-node) {
  margin: 0;
}

.json-tree :deep(.json-toggle) {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  cursor: pointer;
  padding: 2px 8px;
  border-radius: 4px;
  transition: background var(--transition-fast);
  user-select: none;
  margin-bottom: 2px;
}

.json-tree :deep(.json-toggle:hover) {
  background: rgba(0, 0, 0, 0.05);
}

.json-tree :deep(.json-arrow) {
  font-size: 0.5rem;
  color: var(--text-tertiary);
  transition: transform var(--transition-fast);
  display: inline-block;
  width: 10px;
  text-align: center;
}

.json-tree :deep(.json-type) {
  color: var(--text-tertiary);
  font-size: 0.7rem;
  font-weight: 500;
}

.json-tree :deep(.json-count) {
  color: var(--text-tertiary);
  font-size: 0.6875rem;
}

.json-tree :deep(.json-open-bracket) {
  color: var(--text-tertiary);
  font-size: 0.8125rem;
  margin-left: 4px;
}

.json-tree :deep(.json-children) {
  padding-left: 24px;
  border-left: 1px dashed rgba(0, 0, 0, 0.08);
  margin-left: 12px;
  margin-top: 2px;
}

.json-tree :deep(.json-item) {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  padding: 1px 0;
}

.json-tree :deep(.json-key) {
  color: var(--accent);
  margin-right: 4px;
  flex-shrink: 0;
}

.json-tree :deep(.json-colon) {
  color: var(--text-tertiary);
  margin-right: 6px;
  flex-shrink: 0;
}

.json-tree :deep(.json-value-wrapper) {
  flex: 1;
  min-width: 0;
}

.json-tree :deep(.json-value) {
  color: var(--text-primary);
}

.json-tree :deep(.json-string) {
  color: var(--accent-green);
}

.json-tree :deep(.json-number) {
  color: var(--accent-purple);
}

.json-tree :deep(.json-boolean) {
  color: var(--accent-orange);
}

.json-tree :deep(.json-null) {
  color: var(--text-tertiary);
  font-style: italic;
}

.json-tree :deep(.json-bracket-inline) {
  color: var(--text-tertiary);
}

.json-tree :deep(.json-close-bracket) {
  color: var(--text-tertiary);
  display: block;
  margin-top: 2px;
}

.json-tree :deep(.json-comma) {
  color: var(--text-tertiary);
  margin-left: 2px;
}

.error-message {
  color: var(--danger, #FF3B30);
  padding: 20px;
  font-size: 0.875rem;
  background: rgba(255, 59, 48, 0.05);
  border-radius: var(--radius-sm);
  border: 1px solid rgba(255, 59, 48, 0.15);
}

.file-type-badge {
  font-size: 0.6875rem;
  font-weight: 500;
  color: var(--text-secondary);
  padding: 3px 10px;
  background: rgba(0, 0, 0, 0.04);
  border-radius: 100px;
  text-transform: uppercase;
}
</style>