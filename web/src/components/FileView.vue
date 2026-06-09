<template>
  <div class="file-view">
    <div class="file-content" v-if="fileType === 'json'">
      <div class="json-viewer">
        <div class="json-toolbar">
          <button class="btn btn-sm btn-outline" @click="toggleAllJson">{{ allExpanded ? '全部折叠' : '全部展开' }}</button>
          <button class="btn btn-sm btn-outline" @click="copyJson">复制原始</button>
        </div>
        <div v-if="jsonError" class="error">JSON 解析失败: {{ jsonError }}</div>
        <div v-else class="json-tree">
          <JsonNode :value="parsedJson" :path="''" :is-root="true" @toggle="onJsonToggle" />
        </div>
      </div>
    </div>

    <div class="file-content" v-else-if="fileType === 'html'">
      <div class="html-viewer">
        <div class="html-toolbar">
          <button class="btn btn-sm btn-outline" :class="{ 'btn-success': htmlView === 'preview' }" @click="htmlView = 'preview'">预览</button>
          <button class="btn btn-sm btn-outline" :class="{ 'btn-success': htmlView === 'source' }" @click="htmlView = 'source'">源码</button>
        </div>
        <div v-if="htmlView === 'preview'" class="html-preview">
          <iframe :srcdoc="content" sandbox="allow-scripts" class="html-iframe"></iframe>
        </div>
        <div v-else class="html-source">
          <pre><code>{{ content }}</code></pre>
        </div>
      </div>
    </div>

    <div class="file-content" v-else-if="fileType === 'md'">
      <div v-html="renderedMarkdown" @click="onMarkdownClick"></div>
    </div>

    <div class="file-content" v-else>
      <div class="text-viewer">
        <div class="text-toolbar">
          <span class="file-type-badge">.{{ ext }}</span>
          <button class="btn btn-sm btn-outline" @click="copyText">复制</button>
        </div>
        <pre><code>{{ content }}</code></pre>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, h, defineComponent } from 'vue'
import { escapeHtml, escapeHtmlAttr } from '../utils/api.js'
import { renderMarkdown as mdRender, getType } from '../utils/markdown.js'

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

import { watch } from 'vue'
watch(() => props.content, () => {
  if (fileType.value === 'json') parseJson()
}, { immediate: true })

const renderedMarkdown = computed(() => mdRender(props.content))

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
  navigator.clipboard.writeText(props.content)
}

function copyText() {
  navigator.clipboard.writeText(props.content)
}

// Recursive JSON node component
const JsonNode = defineComponent({
  name: 'JsonNode',
  props: {
    value: { required: true },
    path: { type: String, default: '' },
    isRoot: { type: Boolean, default: false }
  },
  emits: ['toggle'],
  setup(props) {
    const isExpanded = ref(true)
    const type = getType(props.value)
    const isContainer = type === 'object' || type === 'array'

    if (isContainer) {
      return () => {
        const keys = Object.keys(props.value)
        const count = keys.length
        const openBracket = type === 'array' ? '[' : '{'
        const closeBracket = type === 'array' ? ']' : '}'

        return h('div', { class: 'json-node' }, [
          h('div', {
            class: 'json-toggle',
            onClick: () => { isExpanded.value = !isExpanded.value }
          }, [
            h('span', { class: ['json-arrow', isExpanded.value ? 'open' : ''] }, '▶'),
            h('span', { class: 'json-type' }, type === 'array' ? 'Array' : 'Object'),
            h('span', { class: 'json-count' }, `(${count} ${count === 1 ? 'item' : 'items'})`)
          ]),
          isExpanded.value
            ? h('div', { class: 'json-children' }, [
                h('span', { class: 'json-bracket' }, openBracket),
                ...keys.map((key, i) =>
                  h('div', { class: 'json-item' }, [
                    h('span', { class: 'json-key' }, `${escapeHtml(String(key))}:`),
                    h(JsonNode, { value: props.value[key], path: props.path ? `${props.path}.${key}` : key }),
                    i < count - 1 ? h('span', { class: 'json-comma' }, ',') : null
                  ])
                ),
                h('span', { class: 'json-bracket' }, closeBracket)
              ])
            : null
        ])
      }
    } else {
      return () => h('span', { class: ['json-value', `json-${type}`] }, escapeHtml(String(props.value)))
    }
  }
})
</script>
