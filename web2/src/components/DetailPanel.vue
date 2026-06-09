<template>
  <aside class="detail-panel" v-if="visible">
    <div class="detail-close" @click="$emit('close')" title="关闭">
      <span v-html="I.x" style="width:16px;height:16px"></span>
    </div>

    <div class="detail-header">
      <div class="uppercase-label">Node Detail</div>
      <div class="detail-title">{{ node?.label || node?.id || '—' }}</div>
      <div class="detail-subtitle">
        <span class="detail-chip" :style="chipStyle(nodeType)">{{ nodeType }}</span>
        <span style="color:var(--text-muted);font-family:var(--font-mono);font-size:11px">#{{ node?.id || '?' }}</span>
      </div>
    </div>

    <div class="detail-body">
      <div v-if="Object.keys(metadata).length === 0" class="empty-state" style="padding:20px 0">
        <span v-html="I.search" style="width:40px;height:40px;color:var(--text-muted)"></span>
        <p>No metadata available</p>
      </div>
      <div v-else class="metadata-grid">
        <div v-for="(value, key) in metadata" :key="key" class="metadata-row">
          <div class="metadata-key">{{ key }}</div>
          <div class="metadata-value">{{ formatValue(value) }}</div>
        </div>
      </div>

      <div v-if="metadata.summary" class="summary-block" style="margin-top:16px">
        <div class="uppercase-label" style="margin-bottom:8px">Summary</div>
        <div class="summary-text">{{ metadata.summary }}</div>
      </div>

      <div v-if="metadata.confidence !== undefined" class="confidence-bar" style="margin-top:16px">
        <div class="uppercase-label" style="margin-bottom:8px">
          Confidence <span style="color:var(--neon-cyan)">{{ Math.round(Number(metadata.confidence) * 100) }}%</span>
        </div>
        <div class="confidence-track">
          <div class="confidence-fill" :style="{ width: Math.min(100, Math.round(Number(metadata.confidence) * 100)) + '%' }"></div>
        </div>
      </div>
    </div>

    <div v-if="related.length > 0" class="detail-related" style="padding:14px 22px;border-top:1px solid var(--border-soft)">
      <div class="uppercase-label" style="margin-bottom:10px">Related nodes</div>
      <div style="display:flex;flex-direction:column;gap:6px">
        <div
          v-for="r in related"
          :key="r.id"
          class="related-row"
          @click="$emit('select-entity', r)"
        >
          <span
            class="related-dot"
            :style="{ background: chipColor(r.type) }"
          ></span>
          <span class="related-label">{{ r.label || r.id }}</span>
          <span class="related-type">{{ r.type }}</span>
        </div>
      </div>
    </div>
  </aside>
</template>

<script setup>
import { computed } from 'vue'
import { I } from '../utils/icons.js'

const props = defineProps({
  visible: { type: Boolean, default: false },
  node: { type: Object, default: null },
  metadata: { type: Object, default: () => ({}) }
})

defineEmits(['close', 'select-entity'])

const nodeType = computed(() => props.node?.type || props.metadata?.type || 'unknown')
const related = computed(() => props.metadata?.related || [])

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
function formatValue(v) {
  if (v === null || v === undefined) return '—'
  if (typeof v === 'object') return JSON.stringify(v, null, 2)
  return String(v)
}
</script>
