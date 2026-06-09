<template>
  <div class="toast-wrap">
    <transition-group name="toast">
      <div
        v-for="t in toasts"
        :key="t.id"
        class="toast"
        :class="t.type"
      >
        <span class="toast-icon">
          <span v-if="t.type === 'success'" v-html="I.circleDot" style="width:16px;height:16px;color:var(--status-ok)"></span>
          <span v-else-if="t.type === 'error'" v-html="I.circleDot" style="width:16px;height:16px;color:var(--status-error)"></span>
          <span v-else-if="t.type === 'warn'" v-html="I.circleDot" style="width:16px;height:16px;color:var(--status-warn)"></span>
          <span v-else v-html="I.circleDot" style="width:16px;height:16px;color:var(--neon-cyan)"></span>
        </span>
        <span class="toast-text">{{ t.message }}</span>
      </div>
    </transition-group>
  </div>
</template>

<script setup>
import { I } from '../utils/icons.js'
defineProps({ toasts: { type: Array, default: () => [] } })
</script>
