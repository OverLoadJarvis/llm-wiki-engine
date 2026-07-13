<template>
  <div class="status-bar">
    <div class="status-left">
      <div v-if="taskRunning" class="spinner"></div>
      <span class="status-text">
        <template v-if="taskRunning && currentFile">{{ currentFile }}</template>
        <template v-else>{{ statusText }}</template>
      </span>
    </div>
    <span class="status-kb">{{ statusKb }}</span>
  </div>
</template>

<script setup>
defineProps({
  statusText: { type: String, default: 'Ready' },
  statusKb: { type: String, default: '' },
  taskRunning: { type: Boolean, default: false },
  currentFile: { type: String, default: '' }
})
</script>

<style scoped>
.status-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 18px;
  height: 28px;
  flex-shrink: 0;
  background: rgba(245, 245, 247, 0.8);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  border-top: 1px solid rgba(0, 0, 0, 0.04);
  font-size: 0.6875rem;
  font-weight: 400;
  color: var(--text-tertiary);
  letter-spacing: 0.01em;
}

.status-left {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
  flex: 1;
}

.status-text {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.status-kb {
  flex-shrink: 0;
  margin-left: 16px;
  color: var(--text-secondary);
}
</style>
