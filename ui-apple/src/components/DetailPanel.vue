<template>
  <div v-if="node" class="detail-panel glass" :style="{ width: panelWidth + 'px' }">
    <!-- Resize Handle -->
    <div class="detail-resize-handle"
         @mousedown="startResize"
         :class="{ active: isResizing }"></div>

    <!-- Header -->
    <div class="detail-header">
      <h3>Node Details</h3>
      <button class="detail-close" @click="$emit('close')">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
        </svg>
      </button>
    </div>

    <!-- Body -->
    <div class="detail-body">
      <!-- Label -->
      <div class="detail-field">
        <div class="detail-field-label">Label</div>
        <div class="detail-field-value label-value">{{ node.label || node.id }}</div>
      </div>

      <!-- Type -->
      <div class="detail-field">
        <div class="detail-field-label">Type</div>
        <div class="detail-field-value">
          <span class="type-badge" :style="{ background: typeColor }">{{ node.type || 'default' }}</span>
        </div>
      </div>

      <!-- Path -->
      <div v-if="node.path" class="detail-field">
        <div class="detail-field-label">Path</div>
        <div class="detail-path">{{ node.path }}</div>
      </div>

      <!-- Preview -->
      <div v-if="node.preview" class="detail-field">
        <div class="detail-field-label">Preview</div>
        <div class="detail-preview-box" v-html="renderedPreview"></div>
      </div>

      <!-- Markdown -->
      <div v-if="node.markdown" class="detail-field">
        <div class="detail-field-label">Content</div>
        <div class="detail-markdown-toggle" @click="mdOpen = !mdOpen">
          <span>View full content</span>
          <svg class="arrow" :class="{ open: mdOpen }" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <polyline points="6 9 12 15 18 9" />
          </svg>
        </div>
        <div class="detail-markdown-content" :class="{ open: mdOpen }" v-html="renderedMarkdown"></div>
      </div>

      <!-- Related Nodes -->
      <div class="detail-related">
        <div class="detail-related-label">Related Nodes ({{ relatedNodes.length }})</div>
        <div class="detail-related-list">
          <span v-if="relatedNodes.length === 0" class="detail-chip-empty">No direct connections</span>
          <button v-for="rel in relatedNodes" :key="String(rel.id)"
                  class="detail-chip"
                  :style="{ borderColor: getRelatedColor(rel) + '40' }"
                  @click="$emit('related-click', rel)">
            {{ rel.label || rel.id }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { renderMarkdown } from '../utils/markdown.js'
import { fileTypeColors } from '../utils/api.js'

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

const typeColor = computed(() => {
  return (fileTypeColors[props.node?.type] || '#8E8E93')
})

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

function getRelatedColor(rel) {
  return fileTypeColors[rel.type] || '#8E8E93'
}

function startResize(e) {
  isResizing.value = true
  startX = e.clientX
  startW = panelWidth.value
  document.addEventListener('mousemove', onResize)
  document.addEventListener('mouseup', stopResize)
}

function onResize(e) {
  const dx = startX - e.clientX
  panelWidth.value = Math.max(280, Math.min(600, startW + dx))
}

function stopResize() {
  isResizing.value = false
  document.removeEventListener('mousemove', onResize)
  document.removeEventListener('mouseup', stopResize)
}
</script>

<style scoped>
.detail-panel {
  position: absolute;
  top: 0;
  right: 0;
  bottom: 0;
  z-index: 50;
  display: flex;
  flex-direction: column;
  border-radius: var(--radius-xl) 0 0 var(--radius-xl);
  border-right: none;
  animation: slideInRight 300ms var(--ease-out-expo);
  overflow: hidden;
}

@keyframes slideInRight {
  from { transform: translateX(20px); opacity: 0; }
  to { transform: translateX(0); opacity: 1; }
}

.detail-resize-handle {
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: 4px;
  cursor: col-resize;
  z-index: 10;
  transition: background var(--transition-fast);
}

.detail-resize-handle:hover,
.detail-resize-handle.active {
  background: var(--accent);
}

.detail-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 18px 20px 14px;
  flex-shrink: 0;
}

.detail-header h3 {
  font-size: 0.8125rem;
  font-weight: 600;
  letter-spacing: 0.02em;
  color: var(--text-secondary);
  text-transform: uppercase;
}

.detail-close {
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

.detail-close:hover {
  background: rgba(0, 0, 0, 0.08);
  color: var(--text-primary);
}

.detail-body {
  flex: 1;
  overflow-y: auto;
  padding: 0 20px 20px;
}

.detail-field {
  margin-bottom: 18px;
}

.detail-field-label {
  font-size: 0.6875rem;
  font-weight: 600;
  color: var(--text-tertiary);
  text-transform: uppercase;
  letter-spacing: 0.04em;
  margin-bottom: 6px;
}

.detail-field-value {
  font-size: 0.875rem;
  color: var(--text-primary);
}

.label-value {
  font-size: 1rem;
  font-weight: 600;
  color: var(--accent);
  letter-spacing: -0.01em;
}

.detail-path {
  font-family: var(--font-mono);
  font-size: 0.75rem;
  color: var(--text-secondary);
  background: rgba(0, 0, 0, 0.03);
  padding: 6px 10px;
  border-radius: 6px;
  word-break: break-all;
}

.detail-preview-box {
  font-size: 0.8125rem;
  line-height: 1.6;
  color: var(--text-secondary);
  background: rgba(0, 0, 0, 0.02);
  border-radius: var(--radius-sm);
  padding: 12px;
  max-height: 160px;
  overflow-y: auto;
}

.detail-markdown-toggle {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 12px;
  background: rgba(0, 0, 0, 0.03);
  border-radius: var(--radius-sm);
  cursor: pointer;
  font-size: 0.8125rem;
  color: var(--text-secondary);
  transition: background var(--transition-fast);
}

.detail-markdown-toggle:hover {
  background: rgba(0, 0, 0, 0.06);
}

.detail-markdown-toggle .arrow {
  transition: transform var(--transition-fast);
}

.detail-markdown-toggle .arrow.open {
  transform: rotate(180deg);
}

.detail-markdown-content {
  max-height: 0;
  overflow: hidden;
  transition: max-height 350ms var(--ease-out-expo);
  font-size: 0.8125rem;
  line-height: 1.7;
  background: rgba(0, 0, 0, 0.02);
  border-radius: 0 0 var(--radius-sm) var(--radius-sm);
}

.detail-markdown-content.open {
  max-height: 400px;
  overflow-y: auto;
  padding: 12px;
}

.detail-related {
  margin-top: 8px;
}

.detail-related-label {
  font-size: 0.6875rem;
  font-weight: 600;
  color: var(--text-tertiary);
  text-transform: uppercase;
  letter-spacing: 0.04em;
  margin-bottom: 10px;
}

.detail-related-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.detail-chip {
  display: inline-flex;
  padding: 5px 12px;
  font-size: 0.75rem;
  font-family: var(--font-sans);
  background: transparent;
  border: 1px solid;
  border-radius: 100px;
  color: var(--text-primary);
  cursor: pointer;
  transition: all var(--transition-fast);
}

.detail-chip:hover {
  background: rgba(0, 122, 255, 0.06);
  transform: translateY(-1px);
}

.detail-chip-empty {
  font-size: 0.8125rem;
  color: var(--text-tertiary);
}
</style>