<template>
  <div v-if="node" class="detail-panel" :style="{ width: panelWidth + 'px' }">
    <div class="detail-resize-handle"
         @mousedown="startResize"
         :class="{ active: isResizing }"></div>

    <div class="detail-header">
      <div class="uppercase-label">Node Detail</div>
      <div class="detail-close" @click="$emit('close')" title="关闭">
        <span v-html="I.x" style="width:16px;height:16px"></span>
      </div>
    </div>

    <div class="detail-body">
      <div class="detail-field">
        <div class="detail-field-label">Label</div>
        <div class="detail-field-value" style="font-size:16px;font-weight:600;color:var(--neon-cyan)">
          {{ node.label || node.id }}
        </div>
      </div>

      <div class="detail-field">
        <div class="detail-field-label">Type</div>
        <div class="detail-field-value">
          <span class="detail-chip" :style="chipStyle(node.type)">{{ node.type || 'default' }}</span>
        </div>
      </div>

      <div v-if="node.path" class="detail-field">
        <div class="detail-field-label">Path</div>
        <div class="detail-path">{{ node.path }}</div>
      </div>

      <div v-if="node.preview" class="detail-field">
        <div class="detail-field-label">Preview</div>
        <div class="detail-preview-box" v-html="renderedPreview"></div>
      </div>

      <div v-if="node.markdown" class="detail-field">
        <div class="detail-field-label">Markdown</div>
        <div class="detail-markdown-toggle" @click="mdOpen = !mdOpen">
          <span>查看完整内容</span>
          <span class="arrow" :class="{ open: mdOpen }">&#9662;</span>
        </div>
        <div class="detail-markdown-content" :class="{ open: mdOpen }" v-html="renderedMarkdown"></div>
      </div>

      <div class="detail-related">
        <div class="uppercase-label" style="margin-bottom:10px">
          相关节点 ({{ relatedNodes.length }})
        </div>
        <div class="detail-related-list">
          <span v-if="relatedNodes.length === 0" class="detail-chip-empty">无直接连接节点</span>
          <button
            v-for="rel in relatedNodes"
            :key="String(rel.id)"
            class="detail-chip"
            :style="{ borderColor: chipColor(rel.type) + '55' }"
            @click="$emit('related-click', rel)"
          >
            {{ rel.label || rel.id }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { renderMarkdown } from '../utils/markdown.js'
import { I } from '../utils/icons.js'

const props = defineProps({
  node: { type: Object, default: null },
  adjacencyMap: { type: Map, default: () => new Map() },
  nodeIndex: { type: Map, default: () => new Map() }
})

defineEmits(['close', 'related-click'])

const panelWidth = ref(380)
const isResizing = ref(false)
const mdOpen = ref(false)

let startX = 0
let startW = 0

const renderedPreview = computed(() =>
  props.node?.preview ? renderMarkdown(props.node.preview) : ''
)

const renderedMarkdown = computed(() =>
  props.node?.markdown ? renderMarkdown(props.node.markdown) : ''
)

const relatedNodes = computed(() => {
  if (!props.node || !props.adjacencyMap || !props.nodeIndex) return []
  const related = props.adjacencyMap.get(props.node.id)
  if (!related) return []
  return Array.from(related)
    .map(id => props.nodeIndex.get(id))
    .filter(n => n && n.id !== props.node.id)
    .sort((a, b) => (a.label || a.id).toString().localeCompare((b.label || b.id).toString()))
})

function chipColor(type) {
  const map = {
    concept: '#8A4BFF',
    entity: '#FF2D95',
    source: '#00F0FF',
    synthesis: '#00FF88'
  }
  return map[type] || '#6B7280'
}

function chipStyle(type) {
  const c = chipColor(type)
  return {
    background: c + '20',
    color: c,
    border: `1px solid ${c}50`
  }
}

function startResize(e) {
  isResizing.value = true
  startX = e.clientX
  startW = panelWidth.value
  document.addEventListener('mousemove', onResize)
  document.addEventListener('mouseup', stopResize)
  document.body.style.cursor = 'col-resize'
  document.body.style.userSelect = 'none'
}

function onResize(e) {
  const dx = startX - e.clientX
  panelWidth.value = Math.min(Math.max(startW + dx, 280), window.innerWidth * 0.7)
}

function stopResize() {
  isResizing.value = false
  document.removeEventListener('mousemove', onResize)
  document.removeEventListener('mouseup', stopResize)
  document.body.style.cursor = ''
  document.body.style.userSelect = ''
}

watch(() => props.node, () => { mdOpen.value = false })
</script>