<template>
  <div class="file-view">
    <div v-if="fileType === 'json'" class="json-viewer">
      <div class="json-toolbar">
        <span class="uppercase-label">JSON · {{ filePath || 'file' }}</span>
        <button class="btn btn-sm btn-ghost" @click="toggleAllJson">{{ allExpanded ? 'Collapse all' : 'Expand all' }}</button>
        <button class="btn btn-sm btn-ghost" @click="copyJson">
          <span v-html="I.copy" style="width:12px;height:12px"></span>
          Copy
        </button>
      </div>
      <div v-if="jsonError" style="color:var(--status-error);padding:12px;border:1px solid rgba(255,61,87,0.3);border-radius:8px;margin-top:12px">
        JSON parse error: {{ jsonError }}
      </div>
      <div v-else class="json-tree" style="background:var(--bg-panel);border:1px solid var(--border-cyan);border-radius:14px;padding:18px 22px;font-family:var(--font-mono);font-size:13px;overflow-x:auto;margin-top:12px">
        <JsonNode :value="parsedJson" :path="''" :is-root="true" :force-expanded="allExpanded" />
      </div>
    </div>

    <div v-else-if="fileType === 'html'" class="html-viewer">
      <div class="html-toolbar">
        <span class="uppercase-label">HTML Preview</span>
        <button class="btn btn-sm" :class="{ 'btn-primary': htmlView === 'preview' }" @click="htmlView = 'preview'">Preview</button>
        <button class="btn btn-sm" :class="{ 'btn-primary': htmlView === 'source' }" @click="htmlView = 'source'">Source</button>
      </div>
      <div v-if="htmlView === 'preview'" style="margin-top:12px;border:1px solid var(--border-cyan);border-radius:14px;overflow:hidden;background:white">
        <iframe :srcdoc="content" sandbox="allow-scripts" style="width:100%;height:70vh;border:0"></iframe>
      </div>
      <pre v-else style="margin-top:12px;background:var(--bg-panel);border:1px solid var(--border-cyan);border-radius:14px;padding:18px 22px;font-family:var(--font-mono);font-size:13px;overflow:auto"><code>{{ content }}</code></pre>
    </div>

    <div v-else-if="fileType === 'md'" class="file-content" @click="onMarkdownClick" v-html="renderedMarkdown"></div>

    <div v-else class="text-viewer">
      <div class="text-toolbar">
        <span class="uppercase-label">.{{ ext }} · raw text</span>
        <button class="btn btn-sm btn-ghost" @click="copyText">
          <span v-html="I.copy" style="width:12px;height:12px"></span>
          Copy
        </button>
      </div>
      <pre style="margin-top:12px;background:var(--bg-panel);border:1px solid var(--border-cyan);border-radius:14px;padding:18px 22px;font-family:var(--font-mono);font-size:13px;overflow:auto"><code>{{ content }}</code></pre>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, h, defineComponent } from 'vue'
import { renderMarkdown } from '../utils/markdown.js'
import { I } from '../utils/icons.js'

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

function parseJson() {
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

const renderedMarkdown = computed(() => renderMarkdown(props.content))

function onMarkdownClick(e) {
  const link = e.target.closest('a.wiki-link')
  if (link) {
    e.preventDefault()
    const target = link.getAttribute('data-wiki-link') || link.textContent
    emit('open-link', target)
  }
}

function toggleAllJson() {
  allExpanded.value = !allExpanded.value
}

function copyJson() {
  navigator.clipboard?.writeText(props.content)
}
function copyText() {
  navigator.clipboard?.writeText(props.content)
}

const JsonNode = defineComponent({
  name: 'JsonNode',
  props: {
    value: { required: true },
    path: { type: String, default: '' },
    isRoot: { type: Boolean, default: false },
    forceExpanded: { type: Boolean, default: true }
  },
  setup(props) {
    const isExpanded = ref(true)
    const type = Array.isArray(props.value) ? 'array' : props.value === null ? 'null' : typeof props.value
    const isContainer = type === 'object' || type === 'array'

    watch(() => props.forceExpanded, (v) => { isExpanded.value = v })

    if (isContainer) {
      return () => {
        const keys = Object.keys(props.value)
        const count = keys.length
        const openBracket = type === 'array' ? '[' : '{'
        const closeBracket = type === 'array' ? ']' : '}'

        const children = keys.map((key, i) => {
          const child = props.value[key]
          const childType = Array.isArray(child) ? 'array' : child === null ? 'null' : typeof child
          const prefixStyle = { color: type === 'array' ? 'var(--text-muted)' : '#00F0FF', fontWeight: 600 }
          const prefixText = type === 'array' ? `[${i}]: ` : `"${key}": `

          let valueNode
          if (childType === 'object' || childType === 'array') {
            valueNode = h(JsonNode, { value: child, path: props.path ? `${props.path}.${key}` : key, 'force-expanded': props.forceExpanded })
          } else {
            const color =
              childType === 'string' ? '#00FF88' :
              childType === 'number' ? '#FFB82B' :
              childType === 'boolean' ? '#FF2D95' : 'var(--text-muted)'
            valueNode = h('span', { style: { color } },
              childType === 'string' ? `"${child}"` : String(child))
          }

          const row = h('div', { style: { margin: '3px 0' } }, [
            h('span', { style: prefixStyle }, prefixText),
            valueNode,
            i < count - 1 ? h('span', { style: { color: 'var(--text-muted)' } }, ',') : null
          ])
          return row
        })

        const indentStyle = props.isRoot
          ? {}
          : { marginLeft: '20px', paddingLeft: '12px', borderLeft: '1px dashed var(--border-soft)' }

        const arrowStyle = {
          display: 'inline-block',
          width: '12px',
          textAlign: 'center',
          transition: 'transform var(--t-fast)',
          transform: isExpanded.value ? 'rotate(90deg)' : 'rotate(0deg)'
        }

        return h('div', { style: indentStyle }, [
          h('div', {
            style: 'display:flex;align-items:center;gap:6px;cursor:pointer;',
            onClick: () => { isExpanded.value = !isExpanded.value }
          }, [
            h('span', { style: arrowStyle }, '▶'),
            h('span', {
              style: 'color:var(--text-muted);font-size:11px;letter-spacing:0.1em;text-transform:uppercase'
            }, `${type} (${count})`)
          ]),
          isExpanded.value ? h('div', {}, [
            h('span', { style: { color: 'var(--text-muted)' } }, openBracket),
            ...children,
            h('span', { style: { color: 'var(--text-muted)' } }, closeBracket)
          ]) : null
        ])
      }
    }

    const color =
      type === 'string' ? '#00FF88' :
      type === 'number' ? '#FFB82B' :
      type === 'boolean' ? '#FF2D95' : 'var(--text-muted)'

    return () => h('span', { style: { color } },
      type === 'string' ? `"${props.value}"` : String(props.value))
  }
})
</script>
