<template>
  <div class="status-bar">
    <span id="statusText">{{ statusText }}</span>
    <span id="statusProject">{{ statusProject }}</span>
  </div>
</template>

<script setup>
defineProps({
  statusText: { type: String, default: '就绪' },
  statusProject: { type: String, default: '' }
})
</script>
