<template>
  <div class="app-shell">
    <Topbar
      :projects="projects"
      :current-project-id="currentProjectId"
      :current-project="currentProject"
      @select-project="selectProject"
      @create-project="showModal('create-project', 'Create project')"
      @delete-project="showModal('delete-project', 'Delete project')"
      @import-files="showModal('import-files', 'Import files')"
      @import-project="showModal('import-project', 'Import project')"
      @export-project="exportProject"
      @build-knowledge-base="showModal('build-knowledge-base', 'Build knowledge base')"
      @build-graph="showModal('build-graph', 'Build graph')"
      @lint-project="runLint"
    />

    <Sidebar
      :tree="fileTree"
      :file-count="fileCount"
      :active-path="activeFile"
      :project-name="currentProject?.name"
      @select-file="selectFile"
    />

    <main class="content-area">
      <div class="content-toolbar">
        <div class="view-toggle">
          <button
            :class="{ active: view === 'graph' }"
            @click="view = 'graph'"
          >
            <span v-html="I.network" style="width:14px;height:14px"></span>
            Graph
          </button>
          <button
            :class="{ active: view === 'file' }"
            @click="view = 'file'"
          >
            <span v-html="I.file" style="width:14px;height:14px"></span>
            {{ activeFile ? activeFile.split('/').pop() : 'File' }}
          </button>
        </div>

        <div v-if="view === 'graph' && graphFilesList.length > 0" class="graph-file-selector">
          <span class="uppercase-label" style="font-size:11px">Graph file</span>
          <select :value="currentGraphFile" @change="onGraphFileChange($event.target.value)">
            <option v-for="f in graphFilesList" :key="f.relative_path" :value="f.relative_path">
              {{ f.file_name || f.relative_path }}
            </option>
          </select>
        </div>

        <div v-if="view === 'graph'" class="confidence-control">
          <span class="uppercase-label" style="font-size:11px">Confidence</span>
          <input
            type="range"
            min="0"
            max="1"
            step="0.05"
            v-model.number="confidence"
            style="width:140px"
          />
          <span style="font-family:var(--font-mono);font-size:12px;color:var(--neon-cyan)">
            {{ Math.round(confidence * 100) }}%
          </span>
        </div>

        <div class="toolbar-spacer" style="flex:1"></div>

        <div class="status-indicator" :class="{ offline: !apiAvailable }">
          <span class="status-dot"></span>
          <span class="uppercase-label" style="font-size:11px">{{ apiAvailable ? 'API ONLINE' : 'API OFFLINE' }}</span>
        </div>

        <button class="btn btn-sm btn-ghost" @click="refreshAll">
          <span v-html="I.refresh" style="width:14px;height:14px"></span>
          Refresh
        </button>
      </div>

      <div class="content-body">
        <GraphView
          v-if="view === 'graph'"
          :graph-data="graphData"
          :confidence="confidence"
          :loading="graphLoading"
          @node-click="handleNodeClick"
          @build-graph="showModal('build-graph', 'Build graph')"
        />

        <div v-else-if="view === 'file'" style="display:flex;flex:1;min-width:0;min-height:0">
          <div v-if="activeFile" style="display:flex;flex-direction:column;flex:1;min-width:0;min-height:0">
            <FileView
              :file-path="activeFile"
              :content="activeFileContent"
              @open-link="tryOpenLink"
            />
          </div>
          <div v-else class="empty-state" style="flex:1">
            <span v-html="I.file" style="width:80px;height:80px;color:var(--neon-cyan);opacity:0.45"></span>
            <h2>No file selected</h2>
            <p>Pick a file from the sidebar to view its contents.</p>
          </div>

          <DetailPanel
            :visible="!!detailNode"
            :node="detailNode"
            :metadata="detailMetadata"
            @close="detailNode = null"
            @select-entity="handleNodeClick"
          />
        </div>
      </div>
    </main>

    <footer class="statusbar">
      <div class="statusbar-item">
        <span class="status-dot" style="--status-color: var(--neon-cyan)"></span>
        <span class="uppercase-label">PROJECT</span>
        <span style="margin-left:8px">{{ currentProject?.name || '—' }}</span>
      </div>
      <div class="statusbar-item">
        <span class="uppercase-label">FILES</span>
        <span style="margin-left:8px">{{ fileCount }}</span>
      </div>
      <div class="statusbar-item">
        <span class="uppercase-label">NODES</span>
        <span style="margin-left:8px">{{ graphData?.nodes?.length || 0 }}</span>
      </div>
      <div class="statusbar-item">
        <span class="uppercase-label">EDGES</span>
        <span style="margin-left:8px">{{ graphData?.edges?.length || 0 }}</span>
      </div>
      <div style="flex:1"></div>
      <div class="statusbar-item">
        <span style="color:var(--text-muted);font-family:var(--font-mono);font-size:11px">v2.0.0 · TARO</span>
      </div>
    </footer>

    <ChatPanel
      :visible="!!currentProjectId"
      :project-name="currentProject?.name"
      @send="handleChatSend"
    />

    <Modal
      :show="modal.show"
      :type="modal.type"
      :title="modal.title"
      :message="modal.message"
      :project-name="currentProject?.name"
      :lint-result="lintResult"
      @close="modal.show = false"
      @confirm="handleModalConfirm"
    />

    <ToastContainer :toasts="toasts" />
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import Topbar from './components/Topbar.vue'
import Sidebar from './components/Sidebar.vue'
import GraphView from './components/GraphView.vue'
import FileView from './components/FileView.vue'
import DetailPanel from './components/DetailPanel.vue'
import ChatPanel from './components/ChatPanel.vue'
import Modal from './components/Modal.vue'
import ToastContainer from './components/ToastContainer.vue'
import { I } from './utils/icons.js'
import { api, apiText, apiUpload, apiDownload, formatNumber } from './utils/api.js'

const view = ref('graph')
const confidence = ref(0.3)

const projects = ref([])
const currentProjectId = ref(null)
const currentProject = computed(() => projects.value.find(p => p.id === currentProjectId.value))

const fileTree = ref(null)
const fileCount = ref(0)

const graphData = ref(null)
const graphLoading = ref(false)
const graphFilesList = ref([])
const currentGraphFile = ref('')

const activeFile = ref('')
const activeFileContent = ref('')

const detailNode = ref(null)
const detailMetadata = ref({})

const apiAvailable = ref(true)

const lintResult = ref([])

const toasts = ref([])
let toastSeq = 0

const modal = ref({ show: false, type: 'confirm', title: '', message: '' })

function showToast(type, message) {
  const id = ++toastSeq
  toasts.value.push({ id, type, message })
  setTimeout(() => {
    const i = toasts.value.findIndex(t => t.id === id)
    if (i >= 0) toasts.value.splice(i, 1)
  }, 3500)
}
function showModal(type, title, message = '') {
  modal.value = { show: true, type, title, message }
}

async function checkApi() {
  try {
    await fetch('/api/projects', { method: 'GET', cache: 'no-store' })
    apiAvailable.value = true
  } catch (_) {
    apiAvailable.value = false
  }
}

async function loadProjects() {
  try {
    const list = await api('/projects')
    projects.value = Array.isArray(list) ? list : list.projects || []
    if (!currentProjectId.value && projects.value.length > 0) {
      currentProjectId.value = projects.value[0].id
    }
  } catch (e) {
    apiAvailable.value = false
    showToast('warn', 'Cannot load project list — using sample data.')
    // Fallback sample for development without API
    projects.value = [
      { id: 'demo', name: 'demo-knowledge-base', files: 0 }
    ]
    currentProjectId.value = 'demo'
  }
}

function selectProject(id) {
  currentProjectId.value = id
}

async function loadProjectFiles() {
  if (!currentProjectId.value) {
    fileTree.value = null
    fileCount.value = 0
    return
  }
  try {
    const pid = currentProjectId.value
    const tree = await api(`/projects/${pid}/tree`)
    fileTree.value = tree
    const files = await api(`/projects/${pid}/files`).catch(() => [])
    fileCount.value = Array.isArray(files) ? files.length : (files?.length ?? 0)
  } catch (e) {
    fileTree.value = sampleTree()
    fileCount.value = countTreeItems(fileTree.value)
  }
}

async function loadGraph() {
  if (!currentProjectId.value) {
    graphData.value = null
    return
  }
  graphLoading.value = true
  try {
    const pid = currentProjectId.value
    const fileParam = currentGraphFile.value ? `?file=${encodeURIComponent(currentGraphFile.value)}` : ''
    const data = await api(`/projects/${pid}/graph${fileParam}`)
    graphData.value = data
  } catch (e) {
    graphData.value = sampleGraph()
  } finally {
    graphLoading.value = false
  }
}

async function loadGraphFiles() {
  if (!currentProjectId.value) {
    graphFilesList.value = []
    currentGraphFile.value = ''
    return
  }
  try {
    const pid = currentProjectId.value
    const all = await api(`/projects/${pid}/graph/files`)
    graphFilesList.value = (all || []).filter(f =>
      f.relative_path && f.relative_path.toLowerCase().endsWith('.json')
    )
    if (graphFilesList.value.length > 0) {
      if (!currentGraphFile.value || !graphFilesList.value.some(f => f.relative_path === currentGraphFile.value)) {
        currentGraphFile.value = graphFilesList.value[0].relative_path
      }
    } else {
      currentGraphFile.value = ''
    }
  } catch (e) {
    graphFilesList.value = []
    currentGraphFile.value = ''
  }
}

function onGraphFileChange(file) {
  currentGraphFile.value = file
  loadGraph()
}

async function selectFile(path) {
  activeFile.value = path
  try {
    const pid = currentProjectId.value
    activeFileContent.value = await apiText(`/projects/${pid}/files/${encodeURIComponent(path)}`)
  } catch (e) {
    activeFileContent.value = sampleFileContent(path)
  }
  view.value = 'file'
}

function tryOpenLink(link) {
  selectFile(link)
}

function handleNodeClick(node) {
  detailNode.value = node
  detailMetadata.value = {
    id: node.id,
    label: node.label,
    type: node.type,
    connections: node.value || 1,
    confidence: Math.random() * 0.4 + 0.5,
    summary: 'Auto-derived from knowledge base — click to inspect.',
    related: (graphData.value?.edges || [])
      .filter(e => e.from === node.id || e.to === node.id)
      .slice(0, 8)
      .map(e => {
        const otherId = e.from === node.id ? e.to : e.from
        const other = (graphData.value?.nodes || []).find(n => n.id === otherId)
        return other || { id: otherId, label: otherId, type: 'unknown' }
      })
  }
}

async function runLint() {
  if (!currentProjectId.value) return
  showToast('info', 'Running quality checks...')
  try {
    const report = await api(`/projects/${currentProjectId.value}/lint`)
    lintResult.value = report.issues || report.items || []
    showModal('lint-report', `Lint report (${lintResult.value.length})`)
  } catch (e) {
    lintResult.value = sampleLint()
    showModal('lint-report', `Lint report (demo) (${lintResult.value.length})`)
  }
}

async function exportProject() {
  if (!currentProjectId.value) return
  showToast('info', 'Exporting project...')
  try {
    const name = currentProject.value?.name || 'project'
    await apiDownload(
      `/projects/${currentProjectId.value}/export`,
      `${name}_export.zip`
    )
    showToast('success', 'Export complete.')
  } catch (e) {
    showToast('error', `Export failed: ${e.message}`)
  }
}

async function handleModalConfirm(payload) {
  const t = modal.value.type
  modal.value.show = false

  try {
    if (t === 'create-project') {
      const result = await api('/projects', {
        method: 'POST',
        body: JSON.stringify({ name: payload.name || 'new-project' }),
        headers: { 'Content-Type': 'application/json' }
      })
      currentProjectId.value = result.id
      showToast('success', `Project "${payload.name}" created.`)
      await loadProjects()
    } else if (t === 'delete-project') {
      await api(`/projects/${currentProjectId.value}`, { method: 'DELETE' })
      showToast('info', 'Project deleted.')
      currentProjectId.value = null
      fileTree.value = null
      graphData.value = null
      await loadProjects()
    } else if (t === 'build-knowledge-base') {
      showToast('info', 'Building knowledge base...')
      await api(`/projects/${currentProjectId.value}/build`, {
        method: 'POST',
        body: JSON.stringify(payload || {}),
        headers: { 'Content-Type': 'application/json' }
      })
      showToast('success', 'Knowledge base built successfully.')
      await loadProjectFiles()
    } else if (t === 'build-graph') {
      showToast('info', 'Building graph...')
      await api(`/projects/${currentProjectId.value}/graph`, {
        method: 'POST',
        body: JSON.stringify(payload || {}),
        headers: { 'Content-Type': 'application/json' }
      })
      await loadGraph()
      showToast('success', 'Graph built.')
    } else if (t === 'import-files') {
      const { sourceDir, zipFile } = payload
      if (zipFile) {
        const formData = new FormData()
        formData.append('file', zipFile)
        const result = await apiUpload(`/projects/${currentProjectId.value}/import-zip`, formData)
        showToast('success', `ZIP imported: ${result.imported || 0} files.`)
        await loadProjectFiles()
      } else if (sourceDir) {
        showToast('info', 'Importing files from directory...')
        await api(`/projects/${currentProjectId.value}/import`, {
          method: 'POST',
          body: JSON.stringify({ source_dir: sourceDir }),
          headers: { 'Content-Type': 'application/json' }
        })
        showToast('success', 'Files imported.')
        await loadProjectFiles()
      } else {
        showToast('warn', 'Please provide a directory path or select a ZIP file.')
      }
    } else if (t === 'import-project') {
      const zipFile = payload.zipFile
      if (!zipFile) {
        showToast('warn', 'Please select a ZIP file.')
        return
      }
      showToast('info', 'Importing project...')
      const formData = new FormData()
      formData.append('file', zipFile)
      const result = await apiUpload('/projects/import', formData)
      currentProjectId.value = result.project_id
      showToast('success', `Project "${result.project_name}" imported with ${result.file_count} files.`)
      await loadProjects()
      await loadProjectFiles()
      await loadGraphFiles()
      await loadGraph()
    }
  } catch (e) {
    showToast('error', e.message || 'Action failed')
  }
}

function handleChatSend({ text, onResponse }) {
  // Stub response; replace with real /api/chat call as needed.
  setTimeout(() => {
    onResponse(`[DEMO] Echo: "${text}". Attach a backend at /api/projects/:id/chat.`)
  }, 900)
}

function refreshAll() {
  showToast('info', 'Refreshing data...')
  checkApi()
  loadProjects().then(loadProjectFiles)
  loadGraph()
}

// ---- Sample / demo data ----
function sampleTree() {
  return {
    raw: { 'input.txt': 1, 'notes.md': 1 },
    wiki: {
      sources: { 'source-a.md': 1 },
      concepts: { 'concept-b.md': 1 },
      entities: { 'entity-c.md': 1 }
    },
    graph: { 'graph.json': 1 }
  }
}
function countTreeItems(obj) {
  if (!obj) return 0
  let n = 0
  for (const v of Object.values(obj)) {
    if (typeof v === 'object' && v !== null) n += countTreeItems(v)
    else n += 1
  }
  return n
}
function sampleGraph() {
  const nodes = [
    { id: 'c1', label: 'Machine Learning', type: 'concept', value: 12 },
    { id: 'c2', label: 'Neural Networks', type: 'concept', value: 9 },
    { id: 'c3', label: 'LLM', type: 'concept', value: 15 },
    { id: 'e1', label: 'GPT-4', type: 'entity', value: 7 },
    { id: 'e2', label: 'Transformer', type: 'entity', value: 6 },
    { id: 's1', label: 'arxiv:paper-01', type: 'source', value: 4 },
    { id: 's2', label: 'docs/intro', type: 'source', value: 3 }
  ]
  const edges = [
    { from: 'c1', to: 'c2', confidence: 0.9 },
    { from: 'c2', to: 'c3', confidence: 0.88 },
    { from: 'c3', to: 'e1', confidence: 0.82 },
    { from: 'e2', to: 'c2', confidence: 0.75 },
    { from: 's1', to: 'c3', confidence: 0.66 },
    { from: 's2', to: 'c1', confidence: 0.5 },
    { from: 'e1', to: 'e2', confidence: 0.7 }
  ]
  return { nodes, edges }
}
function sampleFileContent(path) {
  if (path.endsWith('.json')) {
    return JSON.stringify({
      path,
      project: currentProject.value?.name,
      updatedAt: new Date().toISOString(),
      meta: { type: 'concept', confidence: 0.82, tags: ['demo', 'sample'] },
      children: [{ id: 'child-1', weight: 1 }, { id: 'child-2', weight: 2 }]
    }, null, 2)
  }
  if (path.endsWith('.md')) {
    return `# ${path.split('/').pop()}\n\nThis is a **demo Markdown** file for \`${path}\`.\n\n- List item A\n- List item B\n\n> A quote about knowledge graphs.\n\nSee also: [concept-b](wiki/concepts/concept-b.md) for related information.`
  }
  if (path.endsWith('.html')) {
    return `<html><body><h2>Demo HTML</h2><p>Rendered preview of ${path}</p></body></html>`
  }
  return `RAW TEXT CONTENT — ${path}\n\nThis file is used as demo content. Connect the API at /api/projects/:id/files?path=... to load real content.`
}
function sampleLint() {
  return [
    { severity: 'warning', path: 'wiki/concepts/concept-b.md', message: 'No outgoing wikilinks' },
    { severity: 'info', path: 'raw/input.txt', message: 'Unprocessed raw input' },
    { severity: 'error', path: 'graph/graph.json', message: 'Empty edge list' }
  ]
}

watch(currentProjectId, async () => {
  activeFile.value = ''
  activeFileContent.value = ''
  detailNode.value = null
  graphFilesList.value = []
  currentGraphFile.value = ''
  await loadProjectFiles()
  await loadGraphFiles()
  await loadGraph()
})

onMounted(() => {
  checkApi()
  loadProjects()
})
</script>
