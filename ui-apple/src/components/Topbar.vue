<template>
  <header class="topbar glass-strong">
    <!-- Logo -->
    <div class="logo-group">
      <div class="logo-icon">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">
          <circle cx="12" cy="12" r="3" />
          <path d="M12 1v4m0 14v4M4.22 4.22l2.83 2.83m9.9 9.9l2.83 2.83M1 12h4m14 0h4M4.22 19.78l2.83-2.83m9.9-9.9l2.83-2.83" />
        </svg>
      </div>
      <span class="logo-text">LLM Wiki</span>
    </div>

    <!-- KB Selector -->
    <div class="kb-selector">
      <select :value="selectedKbId" @change="onKbChange" class="kb-select">
        <option value="">Select kb...</option>
        <option v-for="k in kbs" :key="k.id" :value="k.id">
          {{ k.name }} {{ stateLabel(k.state) }}
        </option>
      </select>
      <span v-if="selectedState" class="state-badge" :class="'state-' + selectedState">
        {{ stateLabel(selectedState) }}
      </span>
    </div>

    <!-- Divider -->
    <div class="nav-divider"></div>

    <!-- Left Actions -->
    <div class="nav-actions">
      <button class="btn btn-outline btn-sm" @click="$emit('create-kb')">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <line x1="12" y1="5" x2="12" y2="19" /><line x1="5" y1="12" x2="19" y2="12" />
        </svg>
        New
      </button>
      <button class="btn btn-outline btn-sm" @click="$emit('import-files')" :disabled="taskRunning">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
          <polyline points="17 8 12 3 7 8" /><line x1="12" y1="3" x2="12" y2="15" />
        </svg>
        Import
      </button>
    </div>

    <!-- Spacer -->
    <div class="nav-spacer"></div>

    <!-- Right Tools (collapsible) -->
    <div class="nav-tools">
      <div v-show="toolsExpanded" class="nav-actions nav-actions-tools">
        <button class="btn btn-outline btn-sm" @click="$emit('set-instruction')" title="Build Instructions">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="12" cy="12" r="3" /><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" />
          </svg>
        </button>
        <button class="btn btn-sm" @click="$emit('build-knowledge-base')" :disabled="taskRunning">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2" />
          </svg>
          Build KB
        </button>
        <button class="btn btn-outline btn-sm" @click="$emit('build-graph')" :disabled="taskRunning">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="12" cy="12" r="3" />
            <path d="M12 1v4m0 14v4M4.22 4.22l2.83 2.83m9.9 9.9l2.83 2.83M1 12h4m14 0h4" />
          </svg>
          Build Graph
        </button>
        <button class="btn btn-outline btn-sm" @click="$emit('lint-kb')">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M9 11l3 3L22 4" /><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11" />
          </svg>
          Lint
        </button>
        <button class="btn btn-outline btn-sm" @click="$emit('export-kb')">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
            <polyline points="7 10 12 15 17 10" /><line x1="12" y1="15" x2="12" y2="3" />
          </svg>
          Export KB
        </button>
        <button class="btn btn-outline btn-sm" @click="$emit('import-kb')" :disabled="taskRunning">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <polyline points="16 3 21 3 21 8" /><line x1="4" y1="20" x2="21" y2="3" />
            <polyline points="21 16 21 21 16 21" /><line x1="15" y1="15" x2="21" y2="21" />
            <line x1="4" y1="4" x2="9" y2="9" />
          </svg>
          Import KB
        </button>
        <button class="btn btn-outline btn-sm" @click="$emit('show-query')">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="11" cy="11" r="8" /><line x1="21" y1="21" x2="16.65" y2="16.65" />
          </svg>
          Query
        </button>
        <button class="btn btn-outline btn-sm btn-danger" @click="$emit('delete-kb')">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <polyline points="3 6 5 6 21 6" />
            <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
          </svg>
          Delete
        </button>
      </div>
      <button
        class="btn btn-outline btn-sm nav-tools-toggle"
        :title="toolsExpanded ? 'Collapse tools' : 'Expand tools'"
        @click="toolsExpanded = !toolsExpanded"
      >
        <svg
          width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
          :class="{ 'chevron-open': toolsExpanded }"
        >
          <polyline points="6 9 12 15 18 9" />
        </svg>
        Tools
      </button>
    </div>
  </header>
</template>

<script setup>
import { computed, ref } from 'vue'

const props = defineProps({
  kbs: { type: Array, default: () => [] },
  selectedKbId: { type: [String, Number], default: '' },
  taskRunning: { type: Boolean, default: false }
})

const emit = defineEmits([
  'select-kb', 'create-kb', 'delete-kb', 'import-kb',
  'import-files', 'build-knowledge-base', 'build-graph', 'lint-kb',
  'export-kb', 'show-query', 'set-instruction'
])

const toolsExpanded = ref(false)

const STATE_LABELS = {
  unbuilt: '[Unbuilt]',
  building: '[Building...]',
  completed: '[Ready]'
}

function stateLabel(state) {
  return STATE_LABELS[state] || ''
}

const selectedState = computed(() => {
  if (!props.selectedKbId) return ''
  const k = props.kbs.find(k => k.id === props.selectedKbId)
  return k ? k.state : ''
})

function onKbChange(e) {
  const val = e.target.value
  emit('select-kb', val ? Number(val) : null)
}
</script>

<style scoped>
.topbar {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 0 16px;
  height: 52px;
  flex-shrink: 0;
  border-bottom: 1px solid rgba(0, 0, 0, 0.06);
  z-index: 100;
}

.logo-group {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}

.logo-icon {
  width: 28px;
  height: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--accent);
  color: #fff;
  border-radius: 8px;
}

.logo-text {
  font-size: 0.9375rem;
  font-weight: 700;
  letter-spacing: -0.02em;
  color: var(--text-primary);
}

.kb-selector {
  display: flex;
  align-items: center;
  gap: 8px;
}

.kb-select {
  min-width: 180px;
  max-width: 280px;
  font-size: 0.8125rem;
}

.state-badge {
  display: inline-flex;
  align-items: center;
  padding: 2px 8px;
  font-size: 0.625rem;
  font-weight: 600;
  letter-spacing: 0.03em;
  border-radius: 100px;
  text-transform: uppercase;
}

.state-unbuilt { background: rgba(0,0,0,0.04); color: var(--text-tertiary); }
.state-building { background: rgba(255,149,0,0.12); color: var(--accent-orange); }
.state-completed { background: rgba(52,199,89,0.12); color: var(--accent-green); }

.nav-divider {
  width: 1px;
  height: 24px;
  background: rgba(0, 0, 0, 0.08);
  flex-shrink: 0;
}

.nav-actions {
  display: flex;
  align-items: center;
  gap: 6px;
}

.nav-spacer {
  flex: 1;
  min-width: 8px;
}

.nav-tools {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-shrink: 0;
}

.nav-actions-tools {
  flex-wrap: wrap;
  justify-content: flex-end;
}

.nav-tools-toggle svg {
  transition: transform 0.2s ease;
}

.nav-tools-toggle svg.chevron-open {
  transform: rotate(180deg);
}
</style>
