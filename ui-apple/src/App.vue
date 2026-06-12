<template>
  <div class="app-shell">
    <!-- Top Navigation Bar -->
    <Topbar
      :projects="projects"
      :selected-project-id="currentProjectId"
      @select-project="onSelectProject"
      @create-project="openModal('create')"
      @delete-project="openModal('delete')"
      @import-project="openModal('import-project')"
      @import-files="openModal('import')"
      @build-knowledge-base="buildKnowledgeBase"
      @build-graph="buildGraph"
      @lint-project="openModal('lint')"
      @export-project="exportProject"
      @show-query="openModal('query')"
    />

    <!-- Main Content Area -->
    <div class="main-layout">
      <!-- Sidebar -->
      <Sidebar
        v-if="currentProjectId"
        :tree="fileTree"
        :file-count="fileCount"
        :active-path="currentFilePath"
        @select-file="openFile"
      />

      <!-- Content Panel -->
      <div class="content-area">
        <!-- Content Toolbar -->
        <div class="content-toolbar glass-subtle">
          <div class="toolbar-left">
            <span class="toolbar-title" v-if="currentView === 'graph'">Knowledge Graph</span>
            <span class="toolbar-title" v-else>{{ currentFilePath || 'Select a file' }}</span>
            <span class="badge" v-if="currentProjectName">{{ currentProjectName }}</span>
          </div>

          <div class="toolbar-center" v-if="currentView === 'graph' && graphFilesList.length > 0">
            <select :value="currentGraphFile" @change="onGraphFileChange" class="graph-select">
              <option v-for="f in graphFilesList" :key="f.relative_path" :value="f.relative_path">
                {{ f.file_name }}
              </option>
            </select>
            <div class="confidence-control">
              <span class="confidence-label">Confidence</span>
              <input type="range" min="0" max="1" step="0.05"
                     :value="confidence"
                     @input="confidence = parseFloat($event.target.value)" />
              <span class="confidence-value">{{ confidence.toFixed(2) }}</span>
            </div>
          </div>

          <div class="toolbar-right">
            <button class="btn btn-outline btn-sm" @click="toggleView">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <rect v-if="currentView === 'graph'" x="3" y="3" width="18" height="18" rx="2" />
                <circle v-else cx="12" cy="12" r="3" />
                <path v-if="currentView !== 'graph'" d="M12 1v4m0 14v4M4.22 4.22l2.83 2.83m9.9 9.9l2.83 2.83M1 12h4m14 0h4" />
                <line v-if="currentView === 'graph'" x1="3" y1="9" x2="21" y2="9" />
                <line v-if="currentView === 'graph'" x1="9" y1="3" x2="9" y2="21" />
              </svg>
              {{ currentView === 'graph' ? 'File View' : 'Graph View' }}
            </button>
          </div>
        </div>

        <!-- Content Body -->
        <div class="content-body">
          <GraphView
            v-if="currentView === 'graph'"
            :graph-data="graphData"
            :confidence="confidence"
            :loading="graphLoading"
            ref="graphViewRef"
            @node-click="onNodeClick"
            @build-graph="buildGraph"
          />
          <FileView
            v-else-if="currentView === 'file' && currentFileContent !== null"
            :file-path="currentFilePath"
            :content="currentFileContent"
            @open-link="openWikiLink"
          />
          <div v-else class="empty-state">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
              <polyline points="14 2 14 8 20 8" />
            </svg>
            <p>Select a file from the sidebar to view its content</p>
          </div>

          <DetailPanel
            v-if="currentView === 'graph'"
            :node="selectedNode"
            :adjacency-map="graphAdjacencyMap"
            :node-index="graphNodeIndex"
            @close="selectedNode = null"
            @related-click="onRelatedNodeClick"
          />
        </div>
      </div>
    </div>

    <!-- Status Bar -->
    <StatusBar :status-text="statusText" :status-project="statusProject" />

    <!-- Chat Panel -->
    <ChatPanel
      :current-project-id="currentProjectId"
      :query-api="queryApi"
    />

    <!-- Modal Group -->
    <ModalGroup
      :active="activeModal"
      :project-name="currentProjectName"
      :query-api="queryApi"
      :create-api="createProjectApi"
      :delete-api="deleteProjectApi"
      :import-api="importFilesApi"
      :import-zip-api="importZipApi"
      :import-project-api="importProjectApi"
      :lint-api="lintProjectApi"
      @close="activeModal = ''"
      @project-created="onProjectCreated"
      @project-deleted="onProjectDeleted"
      @files-imported="onFilesImported"
      @project-imported="onProjectImported"
    />
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import Topbar from './components/Topbar.vue'
import Sidebar from './components/Sidebar.vue'
import GraphView from './components/GraphView.vue'
import FileView from './components/FileView.vue'
import DetailPanel from './components/DetailPanel.vue'
import ChatPanel from './components/ChatPanel.vue'
import ModalGroup from './components/ModalGroup.vue'
import StatusBar from './components/StatusBar.vue'
import { api, apiText, apiDownload, apiUpload } from './utils/api.js'

// ── State ─────────────────────────────────────────────────────
const projects = ref([])
const currentProjectId = ref(null)
const currentProjectName = ref('')
const fileTree = ref(null)
const fileCount = ref(0)
const graphData = ref(null)
const graphLoading = ref(false)
const graphFilesList = ref([])
const currentGraphFile = ref('')
const confidence = ref(0.3)
const currentView = ref('graph')
const currentFilePath = ref('')
const currentFileContent = ref(null)
const statusText = ref('Ready')
const statusProject = ref('')
const activeModal = ref('')
const selectedNode = ref(null)
const graphViewRef = ref(null)

const graphAdjacencyMap = computed(() => graphViewRef.value?.adjacencyMap || new Map())
const graphNodeIndex = computed(() => graphViewRef.value?.nodeIndex || new Map())

// ── API Wrappers ──────────────────────────────────────────────
async function queryApi(question) {
  return api(`/projects/${currentProjectId.value}/query`, {
    method: 'POST',
    body: JSON.stringify({ question })
  })
}

async function createProjectApi({ name, description }) {
  return api('/projects', {
    method: 'POST',
    body: JSON.stringify({ name, description })
  })
}

async function deleteProjectApi() {
  return api(`/projects/${currentProjectId.value}`, { method: 'DELETE' })
}

async function importFilesApi(dirPath) {
  return api(`/projects/${currentProjectId.value}/import`, {
    method: 'POST',
    body: JSON.stringify({ source_dir: dirPath })
  })
}

async function importZipApi(formData) {
  return apiUpload(`/projects/${currentProjectId.value}/import-zip`, formData)
}

async function importProjectApi(formData) {
  return apiUpload('/projects/import', formData)
}

async function lintProjectApi() {
  return api(`/projects/${currentProjectId.value}/lint`, { method: 'POST' })
}

// ── Project Management ────────────────────────────────────────
async function loadProjects() {
  try {
    projects.value = await api('/projects')
  } catch (err) {
    statusText.value = `Failed to load projects: ${err.message}`
  }
}

async function loadProject(pid) {
  try {
    const proj = await api(`/projects/${pid}`)
    currentProjectName.value = proj.name || ''
    statusProject.value = `Project: ${proj.name}`
    statusText.value = 'Loading file tree...'
    const tree = await api(`/projects/${pid}/tree`)
    fileTree.value = tree
    const files = await api(`/projects/${pid}/files`).catch(() => [])
    fileCount.value = Array.isArray(files) ? files.length : 0
    statusText.value = 'Loading graph files...'
    try {
      const all = await api(`/projects/${pid}/graph/files`)
      graphFilesList.value = (all || []).filter(f => f.relative_path && f.relative_path.toLowerCase().endsWith('.json'))
      if (graphFilesList.value.length > 0) {
        if (!currentGraphFile.value || !graphFilesList.value.some(f => f.relative_path === currentGraphFile.value)) {
          currentGraphFile.value = graphFilesList.value[0].relative_path
        }
      }
    } catch (e) {
      graphFilesList.value = []
    }
    statusText.value = 'Loading graph...'
    await loadGraph(pid)
    statusText.value = 'Ready'
  } catch (err) {
    statusText.value = `Error: ${err.message}`
  }
}

async function loadGraph(pid) {
  graphLoading.value = true
  try {
    const data = await api(`/projects/${pid}/graph?file=${encodeURIComponent(currentGraphFile.value)}`)
    graphData.value = data
  } catch (err) {
    graphData.value = null
  } finally {
    graphLoading.value = false
  }
}

function resetView() {
  fileTree.value = null
  graphData.value = null
  currentFilePath.value = ''
  currentFileContent.value = null
  selectedNode.value = null
  graphFilesList.value = []
  currentGraphFile.value = ''
  statusProject.value = ''
}

async function onSelectProject(pid) {
  currentProjectId.value = pid
  if (pid === null || pid === '' || pid === undefined) {
    resetView()
    return
  }
  await loadProject(pid)
}

async function openFile(relPath) {
  currentFilePath.value = relPath
  try {
    statusText.value = `Loading: ${relPath}`
    const content = await apiText(`/projects/${currentProjectId.value}/files/${encodeURIComponent(relPath)}`)
    currentFileContent.value = content
    currentView.value = 'file'
    statusText.value = `Opened: ${relPath}`
  } catch (err) {
    statusText.value = `Load failed: ${err.message}`
  }
}

function toggleView() {
  if (currentView.value === 'graph') {
    if (currentFilePath.value) {
      currentView.value = 'file'
    }
  } else {
    currentView.value = 'graph'
  }
}

async function onGraphFileChange(e) {
  currentGraphFile.value = e.target.value
  if (currentProjectId.value) {
    await loadGraph(currentProjectId.value)
  }
}

function onNodeClick(node) {
  selectedNode.value = node
}

function onRelatedNodeClick(rel) {
  selectedNode.value = rel
}

async function openWikiLink(target) {
  if (!currentProjectId.value) return
  await openFile(target)
}

async function buildKnowledgeBase() {
  if (!currentProjectId.value) return alert('Please select a project first')
  if (!confirm('Build knowledge base? This may take a while.')) return
  statusText.value = 'Building knowledge base...'
  try {
    const result = await api(`/projects/${currentProjectId.value}/build`, { method: 'POST' })
    statusText.value = `Build complete: ${result.ingested} files ingested`
    await loadProject(currentProjectId.value)
  } catch (err) {
    statusText.value = `Build failed: ${err.message}`
    alert(`Build failed: ${err.message}`)
  }
}

async function buildGraph() {
  if (!currentProjectId.value) return alert('Please select a project first')
  statusText.value = 'Building graph...'
  try {
    const result = await api(`/projects/${currentProjectId.value}/graph/build`, { method: 'POST' })
    statusText.value = `Graph built: ${result.n_nodes} nodes, ${result.n_edges} edges`
    await loadGraph(currentProjectId.value)
  } catch (err) {
    statusText.value = `Graph build failed: ${err.message}`
  }
}

async function exportProject() {
  if (!currentProjectId.value) return alert('Please select a project first')
  statusText.value = 'Exporting project...'
  try {
    await apiDownload(
      `/projects/${currentProjectId.value}/export`,
      `${currentProjectName.value}_export.zip`
    )
    statusText.value = 'Export complete'
  } catch (err) {
    statusText.value = `Export failed: ${err.message}`
    alert(`Export failed: ${err.message}`)
  }
}

function openModal(name) {
  if (!currentProjectId.value && ['delete', 'import', 'lint', 'query'].includes(name)) {
    alert('Please select a project first')
    return
  }
  activeModal.value = name
}

async function onProjectCreated(pid) {
  await loadProjects()
  await onSelectProject(pid)
  activeModal.value = ''
}

async function onProjectDeleted() {
  resetView()
  currentProjectId.value = null
  await loadProjects()
  activeModal.value = ''
}

async function onFilesImported() {
  await loadProject(currentProjectId.value)
  activeModal.value = ''
}

async function onProjectImported(pid) {
  await loadProjects()
  await onSelectProject(pid)
  activeModal.value = ''
}

onMounted(() => {
  loadProjects()
})
</script>

<style scoped>
.app-shell {
  display: flex;
  flex-direction: column;
  height: 100vh;
  width: 100vw;
  overflow: hidden;
  background: var(--bg-primary);
}

.main-layout {
  display: flex;
  flex: 1;
  overflow: hidden;
  padding: 8px;
  gap: 8px;
}

.content-area {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  min-width: 0;
}

.content-toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 18px;
  border-radius: var(--radius-lg);
  margin-bottom: 8px;
  flex-shrink: 0;
}

.toolbar-left {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}

.toolbar-title {
  font-size: 0.8125rem;
  font-weight: 600;
  color: var(--text-primary);
  letter-spacing: -0.01em;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 400px;
}

.toolbar-center {
  display: flex;
  align-items: center;
  gap: 16px;
  flex: 1;
  justify-content: center;
}

.toolbar-right {
  display: flex;
  align-items: center;
  margin-left: auto;
}

.graph-select {
  width: 220px;
  font-size: 0.8125rem;
}

.confidence-control {
  display: flex;
  align-items: center;
  gap: 8px;
}

.confidence-label {
  font-size: 0.6875rem;
  font-weight: 500;
  color: var(--text-tertiary);
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.confidence-control input[type="range"] {
  width: 80px;
  accent-color: var(--accent);
}

.confidence-value {
  font-size: 0.75rem;
  font-weight: 500;
  color: var(--accent);
  font-variant-numeric: tabular-nums;
  min-width: 36px;
}

.content-body {
  flex: 1;
  overflow: hidden;
  position: relative;
  border-radius: var(--radius-xl);
  background: var(--bg-elevated);
}
</style>