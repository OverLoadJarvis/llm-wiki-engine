<template>
  <div class="topbar">
    <div class="brand">
      <div class="brand-logo">
        <div class="brand-logo-inner"></div>
      </div>
      <div>
        <div class="brand-title">NEXUS // LLM WIKI</div>
        <div class="brand-subtitle">KNOWLEDGE GRAPH ENGINE v2.0</div>
      </div>
    </div>

    <div class="topbar-center">
      <div class="project-select" @click.stop>
        <div class="select-wrapper" @click="projectDropdownOpen = !projectDropdownOpen">
          <div style="flex:1;min-width:0">
            <div class="project-select-label">Active Project</div>
            <div class="project-select-value">{{ currentProject?.name || '— no project —' }}</div>
          </div>
          <span v-if="currentProject" class="state-indicator" :class="'state-' + currentProject.state">{{ stateLabel(currentProject.state) }}</span>
          <span v-html="I.chevronDown" style="width:16px;height:16px;color:var(--text-muted)"></span>
        </div>
        <div v-if="projectDropdownOpen" class="project-select-dropdown" @click.stop>
          <div v-if="projects.length === 0" class="project-select-item" style="color:var(--text-muted)">
            No projects available
          </div>
          <div
            v-for="p in projects"
            :key="p.id"
            class="project-select-item"
            :class="{ active: p.id === currentProjectId }"
            @click="selectProject(p.id)"
          >
            <span style="color:var(--neon-cyan);font-family:var(--font-mono);font-size:11px;margin-right:8px">#{{ p.id }}</span>
            {{ p.name }}
            <span style="margin-left:auto;opacity:0.6" :style="{ color: stateColor(p.state) }">{{ stateLabel(p.state) }}</span>
          </div>
          <div style="height:1px;background:var(--border-soft);margin:8px 0"></div>
          <div class="project-select-item" @click="$emit('create-project')">
            <span style="color:var(--neon-green);margin-right:8px">+</span>
            <span style="color:var(--neon-green)">Create new project</span>
          </div>
        </div>
      </div>
    </div>

    <div class="topbar-actions">
      <button class="topbar-action" title="导入文件" @click="$emit('import-files')">
        <span v-html="I.download"></span>
      </button>
      <button class="topbar-action" title="导入项目" @click="$emit('import-project')">
        <span v-html="I.plus"></span>
      </button>
      <button class="topbar-action" title="导出项目" @click="$emit('export-project')">
        <span v-html="I.download" style="transform:rotate(180deg)"></span>
      </button>
      <button class="topbar-action" title="构建知识库" @click="$emit('build-knowledge-base')">
        <span v-html="I.bolt"></span>
      </button>
      <button class="topbar-action" title="构建图谱" @click="$emit('build-graph')">
        <span v-html="I.network"></span>
      </button>
      <button class="topbar-action" title="质量检查" @click="$emit('lint-project')">
        <span v-html="I.shield"></span>
      </button>
      <button class="topbar-action" title="删除项目" @click="$emit('delete-project')" style="color:var(--status-error)">
        <span v-html="I.trash"></span>
      </button>
    </div>
  </div>
</template>

<script setup>
import { I } from '../utils/icons.js'
import { ref, onMounted, onBeforeUnmount } from 'vue'

defineProps({
  projects: { type: Array, default: () => [] },
  currentProjectId: { type: [String, Number], default: null },
  currentProject: { type: Object, default: null }
})
const emit = defineEmits(['select-project', 'create-project', 'delete-project', 'import-files', 'import-project', 'export-project', 'build-knowledge-base', 'build-graph', 'lint-project'])

const STATE_LABELS = {
  unbuilt: 'unbuilt',
  building: 'building...',
  completed: 'completed',
}

const STATE_COLORS = {
  unbuilt: 'var(--text-muted)',
  building: 'var(--neon-yellow, #f0c040)',
  completed: 'var(--neon-green, #00ff88)',
}

function stateLabel(state) {
  return STATE_LABELS[state] || state || ''
}

function stateColor(state) {
  return STATE_COLORS[state] || 'var(--text-muted)'
}

const projectDropdownOpen = ref(false)

function selectProject(id) {
  projectDropdownOpen.value = false
  emit('select-project', id)
}

function onDocClick(e) {
  if (!e.target.closest('.project-select')) projectDropdownOpen.value = false
}

onMounted(() => document.addEventListener('click', onDocClick))
onBeforeUnmount(() => document.removeEventListener('click', onDocClick))
</script>
