<template>
  <div class="status-bar">
    <span class="status-text">{{ statusText }}</span>
    <span class="status-project">{{ statusProject }}</span>
  </div>
</template>

<script setup>
defineProps({
  statusText: { type: String, default: 'Ready' },
  statusProject: { type: String, default: '' }
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

.status-text {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.status-project {
  flex-shrink: 0;
  margin-left: 16px;
  color: var(--text-secondary);
}
</style>