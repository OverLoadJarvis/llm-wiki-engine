<template>
  <div class="topbar">
    <div class="logo">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <circle cx="12" cy="12" r="3"/><path d="M12 1v4m0 14v4M4.22 4.22l2.83 2.83m9.9 9.9l2.83 2.83M1 12h4m14 0h4M4.22 19.78l2.83-2.83m9.9-9.9l2.83-2.83"/>
      </svg>
      LLM Wiki
    </div>
    <div class="project-selector">
      <select :value="selectedProjectId" @change="onProjectChange">
        <option value="">选择项目...</option>
        <option v-for="p in projects" :key="p.id" :value="p.id">{{ p.name }}</option>
      </select>
      <button class="btn btn-sm" @click="$emit('create-project')">+ 新建</button>
      <button class="btn btn-sm btn-outline" @click="$emit('import-files')">导入文件</button>
      <button class="btn btn-sm btn-outline" style="color:var(--danger);border-color:var(--danger);" @click="$emit('delete-project')">删除项目</button>
    </div>
    <div style="flex:1"></div>
    <button class="btn btn-sm btn-outline" @click="$emit('build-knowledge-base')">构建知识库</button>
    <button class="btn btn-sm btn-outline" @click="$emit('build-graph')">构建图谱</button>
    <button class="btn btn-sm btn-outline" @click="$emit('lint-project')">质量检查</button>
      <button class="btn btn-sm btn-outline" @click="$emit('export-project')">导出项目</button>
      <button class="btn btn-sm btn-outline" @click="$emit('show-query')">查询</button>
  </div>
</template>

<script setup>
defineProps({
  projects: { type: Array, default: () => [] },
  selectedProjectId: { type: [String, Number], default: '' }
})

const emit = defineEmits([
  'select-project',
  'create-project',
  'delete-project',
  'import-files',
  'build-knowledge-base',
  'build-graph',
  'lint-project',
  'export-project',
  'show-query'
])

function onProjectChange(e) {
  const val = e.target.value
  emit('select-project', val ? Number(val) : null)
}
</script>
