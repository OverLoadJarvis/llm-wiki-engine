<template>
  <Transition name="panel-slide">
    <div v-if="visible && !minimized" class="task-panel glass-strong">
      <div class="task-header">
        <div class="task-title-row">
          <div v-if="running" class="spinner"></div>
          <span class="task-title">{{ title }}</span>
          <span v-if="total > 0" class="task-progress-text">{{ current }}/{{ total }}</span>
        </div>
        <div class="task-actions">
          <button class="btn-icon" title="Minimize" @click="$emit('minimize')">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <line x1="5" y1="12" x2="19" y2="12" />
            </svg>
          </button>
          <button v-if="!running" class="btn-icon" title="Close" @click="$emit('close')">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>
        </div>
      </div>

      <div v-if="total > 0" class="progress-bar-track">
        <div class="progress-bar-fill" :style="{ width: progressPercent + '%' }"></div>
      </div>

      <div v-if="currentFile && running" class="task-current-file">{{ currentFile }}</div>

      <div class="task-log-list">
        <div
          v-for="(log, i) in logs"
          :key="i"
          class="task-log-item"
          :class="'log-' + log.status"
        >
          <span class="log-icon">{{ logIcon(log.status) }}</span>
          <span class="log-text">{{ log.message }}</span>
        </div>
      </div>

      <div v-if="summary && !running" class="task-summary" :class="summaryClass">
        {{ summary }}
      </div>
    </div>
  </Transition>

  <Transition name="panel-slide">
    <button
      v-if="visible && minimized"
      class="task-minimized glass-strong"
      @click="$emit('restore')"
    >
      <div v-if="running" class="spinner"></div>
      <span>{{ title }}</span>
      <span v-if="total > 0" class="task-progress-text">{{ current }}/{{ total }}</span>
    </button>
  </Transition>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  visible: { type: Boolean, default: false },
  minimized: { type: Boolean, default: false },
  running: { type: Boolean, default: false },
  title: { type: String, default: 'Task' },
  current: { type: Number, default: 0 },
  total: { type: Number, default: 0 },
  currentFile: { type: String, default: '' },
  logs: { type: Array, default: () => [] },
  summary: { type: String, default: '' },
  hasErrors: { type: Boolean, default: false }
})

defineEmits(['close', 'minimize', 'restore'])

const progressPercent = computed(() => {
  if (props.total <= 0) return props.running ? 5 : 100
  return Math.min(100, Math.round((props.current / props.total) * 100))
})

const summaryClass = computed(() => props.hasErrors ? 'summary-error' : 'summary-ok')

function logIcon(status) {
  if (status === 'ok') return '✓'
  if (status === 'error') return '✗'
  if (status === 'skip') return '–'
  if (status === 'info') return '·'
  return '›'
}
</script>

<style scoped>
.task-panel {
  position: fixed;
  bottom: 40px;
  right: 16px;
  width: 380px;
  max-height: 420px;
  display: flex;
  flex-direction: column;
  border-radius: var(--radius-lg);
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.12);
  z-index: 200;
  overflow: hidden;
}

.task-minimized {
  position: fixed;
  bottom: 40px;
  right: 16px;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 14px;
  border-radius: 100px;
  border: none;
  cursor: pointer;
  font-size: 0.75rem;
  font-weight: 500;
  color: var(--text-primary);
  z-index: 200;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.1);
}

.task-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 14px 8px;
  flex-shrink: 0;
}

.task-title-row {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.task-title {
  font-size: 0.8125rem;
  font-weight: 600;
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.task-progress-text {
  font-size: 0.6875rem;
  font-weight: 600;
  color: var(--text-tertiary);
  flex-shrink: 0;
}

.task-actions {
  display: flex;
  gap: 4px;
  flex-shrink: 0;
}

.btn-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  border: none;
  background: transparent;
  border-radius: 6px;
  cursor: pointer;
  color: var(--text-tertiary);
  transition: background var(--transition-fast);
}

.btn-icon:hover {
  background: rgba(0, 0, 0, 0.06);
  color: var(--text-primary);
}

.progress-bar-track {
  height: 3px;
  background: rgba(0, 0, 0, 0.06);
  margin: 0 14px;
  border-radius: 2px;
  overflow: hidden;
  flex-shrink: 0;
}

.progress-bar-fill {
  height: 100%;
  background: var(--accent);
  border-radius: 2px;
  transition: width 0.3s ease;
}

.task-current-file {
  padding: 6px 14px 0;
  font-size: 0.6875rem;
  color: var(--text-secondary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex-shrink: 0;
}

.task-log-list {
  flex: 1;
  overflow-y: auto;
  padding: 8px 14px;
  min-height: 80px;
  max-height: 240px;
}

.task-log-item {
  display: flex;
  align-items: flex-start;
  gap: 6px;
  font-size: 0.6875rem;
  line-height: 1.5;
  padding: 2px 0;
  color: var(--text-secondary);
}

.log-icon {
  flex-shrink: 0;
  width: 12px;
  text-align: center;
  font-weight: 700;
}

.log-ok .log-icon { color: var(--accent-green); }
.log-error { color: var(--danger); }
.log-error .log-icon { color: var(--danger); }
.log-skip .log-icon { color: var(--text-tertiary); }
.log-info .log-icon { color: var(--accent); }

.log-text {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.task-summary {
  padding: 8px 14px 12px;
  font-size: 0.75rem;
  font-weight: 500;
  border-top: 1px solid rgba(0, 0, 0, 0.06);
  flex-shrink: 0;
}

.summary-ok { color: var(--accent-green); }
.summary-error { color: var(--accent-orange); }

.panel-slide-enter-active,
.panel-slide-leave-active {
  transition: transform 0.25s ease, opacity 0.25s ease;
}

.panel-slide-enter-from,
.panel-slide-leave-to {
  transform: translateY(12px);
  opacity: 0;
}
</style>
