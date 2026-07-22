<template>
  <div class="app-shell">
    <!-- Top Navigation Bar -->
    <Topbar
      :kbs="kbs"
      :selected-kb-id="currentKbId"
      :task-running="taskRunning"
      @select-kb="onSelectKb"
      @create-kb="openModal('create')"
      @delete-kb="openModal('delete')"
      @import-kb="openModal('import-kb')"
      @import-files="openModal('import')"
      @build-knowledge-base="buildKnowledgeBase"
      @build-graph="buildGraph"
      @lint-kb="openModal('lint')"
      @export-kb="exportKb"
      @show-query="openChat"
      @set-instruction="openModal('instruction')"
      @llm-settings="openModal('llm-settings')"
    />

    <!-- Main Content Area -->
    <div class="main-layout">
      <!-- Sidebar -->
      <Sidebar
        v-if="currentKbId"
        :tree="fileTree"
        :file-count="fileCount"
        :active-path="currentFilePath"
        :collapsed="sidebarCollapsed"
        @select-file="openFile"
      />

      <!-- Content Panel -->
      <div class="content-area">
        <!-- Content Toolbar -->
        <div class="content-toolbar glass-subtle">
          <div class="toolbar-left">
            <button
              v-if="currentKbId"
              class="btn btn-outline btn-sm toolbar-icon-btn"
              :title="sidebarCollapsed ? 'Show files' : 'Hide files'"
              @click="toggleSidebar"
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <rect x="3" y="3" width="18" height="18" rx="2" />
                <line x1="9" y1="3" x2="9" y2="21" />
                <polyline v-if="!sidebarCollapsed" points="15 8 12 12 15 16" />
              </svg>
            </button>
            <span class="toolbar-title" v-if="currentView === 'graph'">Knowledge Graph</span>
            <span class="toolbar-title" v-else>{{ currentFilePath || 'Select a file' }}</span>
            <span class="badge" v-if="currentKbName">{{ currentKbName }}</span>
          </div>

          <div class="toolbar-center" v-if="currentView === 'graph'">
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
            <button
              class="btn btn-outline btn-sm"
              :class="{ 'btn-active': chatOpen }"
              title="Chat"
              @click="toggleChat"
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
              </svg>
              Chat
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
            :kb-id="currentKbId"
            @open-link="openWikiLink"
            @save-file="onSaveFile"
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

      <!-- Chat Dock -->
      <ChatPanel
        v-model:open="chatOpen"
        :current-kb-id="currentKbId"
        :query-api="queryApi"
        :open-wiki-link="openWikiLink"
      />
    </div>

    <!-- Status Bar -->
    <StatusBar
      :status-text="statusText"
      :status-kb="statusKb"
      :task-running="taskRunning"
      :current-file="activeTask?.currentFile || ''"
    />

    <!-- Task Progress Panel -->
    <TaskProgressPanel
      v-if="activeTask"
      :visible="activeTask.visible"
      :minimized="activeTask.minimized"
      :running="activeTask.running"
      :title="activeTask.title"
      :current="activeTask.current"
      :total="activeTask.total"
      :current-file="activeTask.currentFile"
      :logs="activeTask.logs"
      :summary="activeTask.summary"
      :has-errors="activeTask.hasErrors"
      @close="closeTaskPanel"
      @minimize="activeTask.minimized = true"
      @restore="activeTask.minimized = false"
    />

    <!-- Modal Group -->
    <ModalGroup
      :active="activeModal"
      :kb-name="currentKbName"
      :task-running="taskRunning"
      :create-api="createKbApi"
      :delete-api="deleteKbApi"
      :lint-api="lintKbApi"
      :instruction-api="getInstructionApi"
      :set-instruction-api="setInstructionApi"
      :get-llm-settings-api="getLlmSettingsApi"
      :set-llm-settings-api="setLlmSettingsApi"
      :test-llm-settings-api="testLlmSettingsApi"
      @close="activeModal = ''"
      @kb-created="onKbCreated"
      @kb-deleted="onKbDeleted"
      @import-stream="onImportStream"
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
import TaskProgressPanel from './components/TaskProgressPanel.vue'
import { api, apiText, apiDownload } from './utils/api.js'
import { consumeSSE, consumeSSEUpload } from './utils/sse.js'

// ── State ─────────────────────────────────────────────────────
const kbs = ref([])
const currentKbId = ref(null)
const currentKbName = ref('')
const fileTree = ref(null)
const fileCount = ref(0)
const graphData = ref(null)
const graphLoading = ref(false)
const currentGraphFile = ref('')
const confidence = ref(0.3)
const currentView = ref('graph')
const currentFilePath = ref('')
const currentFileContent = ref(null)
const statusText = ref('Ready')
const statusKb = ref('')
const activeModal = ref('')
const selectedNode = ref(null)
const graphViewRef = ref(null)
const activeTask = ref(null)
const sidebarCollapsed = ref(localStorage.getItem('sidebarCollapsed') === '1')
const chatOpen = ref(false)

const taskRunning = computed(() => activeTask.value?.running ?? false)

const graphAdjacencyMap = computed(() => graphViewRef.value?.adjacencyMap || new Map())
const graphNodeIndex = computed(() => graphViewRef.value?.nodeIndex || new Map())

// ── API Wrappers ──────────────────────────────────────────────
async function queryApi(question, onChunk) {
  const url = `/api/kbs/${currentKbId.value}/query`
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question, stream: !!onChunk })
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: res.statusText }))
    throw new Error(err.error || `HTTP ${res.status}`)
  }

  if (onChunk) {
    const reader = res.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    let fullAnswer = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })

      // Parse SSE lines
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''
      for (const line of lines) {
        if (line.startsWith('data: ')) {
          try {
            const data = JSON.parse(line.slice(6))
            if (data.error) {
              throw new Error(data.error)
            }
            if (data.done) {
              return { answer: fullAnswer }
            }
            if (data.chunk) {
              fullAnswer += data.chunk
              onChunk(data.chunk)
            }
          } catch (e) {
            // Re-throw server errors, ignore JSON parse errors on incomplete lines
            if (e instanceof SyntaxError) continue
            throw e
          }
        }
      }
    }
    return { answer: fullAnswer }
  }

  return res.json()
}

async function createKbApi({ name, description }) {
  return api('/kbs', {
    method: 'POST',
    body: JSON.stringify({ name, description })
  })
}

async function deleteKbApi() {
  return api(`/kbs/${currentKbId.value}`, { method: 'DELETE' })
}

// ── Task / SSE ────────────────────────────────────────────────
function createTask(type, title) {
  activeTask.value = {
    type,
    title,
    running: true,
    current: 0,
    total: 0,
    currentFile: '',
    logs: [],
    summary: '',
    hasErrors: false,
    minimized: false,
    visible: true
  }
}

function handleTaskEvent(event) {
  const task = activeTask.value
  if (!task) return

  switch (event.event) {
    case 'start':
      task.total = event.total || 0
      if (event.kb_name) {
        const skipped = event.skipped ? `, ${event.skipped} already ingested` : ''
        task.logs.push({
          status: 'info',
          message: `${event.kb_name}: ${event.total} to process${skipped}`
        })
      }
      break
    case 'uploading':
      task.logs.push({ status: 'info', message: 'Uploading ZIP...' })
      break
    case 'extracting':
      task.logs.push({ status: 'info', message: 'Extracting archive...' })
      break
    case 'import_start':
      task.logs.push({ status: 'info', message: `Importing from ${event.source_dir}` })
      break
    case 'file_start':
      task.current = Math.max(0, (event.index || 1) - 1)
      task.total = event.total || task.total
      task.currentFile = event.file || ''
      statusText.value = `Processing: ${event.file}`
      break
    case 'file_done':
    case 'file_imported':
      task.current = event.index ?? task.current + 1
      task.logs.push({ status: 'ok', message: event.file })
      break
    case 'file_skipped':
      task.logs.push({ status: 'skip', message: `${event.file} (skipped)` })
      break
    case 'file_error':
      task.hasErrors = true
      task.logs.push({ status: 'error', message: `${event.file}: ${event.error}` })
      break
    case 'graph_start':
      task.logs.push({ status: 'info', message: 'Building knowledge graph...' })
      task.currentFile = 'Building graph...'
      break
    case 'graph_done':
      task.logs.push({
        status: 'info',
        message: `Graph: ${event.n_nodes} nodes, ${event.n_edges} edges`
      })
      break
    case 'graph_error':
      task.hasErrors = true
      task.logs.push({ status: 'error', message: `Graph: ${event.error}` })
      break
    default:
      break
  }
}

function finishTask(result, type) {
  const task = activeTask.value
  if (!task) return
  task.running = false
  task.currentFile = ''
  if (task.total > 0) task.current = task.total

  if (type === 'build') {
    if (result?.status === 'up_to_date') {
      const skipped = result?.skipped ?? 0
      task.summary = `Up to date: ${skipped} file(s) already ingested`
    } else {
      const ingested = result?.ingested ?? 0
      const skipped = result?.skipped ?? 0
      const errCount = Array.isArray(result?.errors) ? result.errors.length : 0
      task.summary = `Build complete: ${ingested} ingested${skipped ? `, ${skipped} skipped` : ''}${errCount ? `, ${errCount} errors` : ''}`
    }
    statusText.value = task.summary
  } else if (type === 'import' || type === 'import_zip') {
    const imported = result?.imported ?? 0
    const skipped = result?.skipped ?? 0
    const errors = result?.errors ?? 0
    task.summary = `Imported ${imported}, skipped ${skipped}, errors ${errors}`
    statusText.value = task.summary
  } else if (type === 'import_kb') {
    task.summary = `KB "${result?.kb_name}" imported (${result?.file_count} files)`
    statusText.value = task.summary
  }
}

function failTask(err) {
  const task = activeTask.value
  if (!task) return
  task.running = false
  task.hasErrors = true
  task.summary = `Failed: ${err.message}`
  task.logs.push({ status: 'error', message: err.message })
  statusText.value = task.summary
}

function closeTaskPanel() {
  if (activeTask.value?.running) return
  activeTask.value = null
}

async function lintKbApi() {
  return api(`/kbs/${currentKbId.value}/lint`, { method: 'POST' })
}

async function getInstructionApi() {
  return api(`/kbs/${currentKbId.value}/instruction`)
}

async function setInstructionApi(instruction) {
  return api(`/kbs/${currentKbId.value}/instruction`, {
    method: 'PUT',
    body: JSON.stringify({ instruction })
  })
}

async function getLlmSettingsApi() {
  console.log('[api] GET /settings/llm')
  try {
    const res = await api('/settings/llm')
    console.log('[api] GET /settings/llm ok', { api_key_set: !!res.api_key_set })
    return res
  } catch (err) {
    console.error('[api] GET /settings/llm failed', err.message)
    throw err
  }
}

async function setLlmSettingsApi(body) {
  console.log('[api] PUT /settings/llm', {
    base_url: body.base_url,
    model: body.model,
    model_fast: body.model_fast,
    api_key_provided: !!body.api_key
  })
  try {
    const res = await api('/settings/llm', {
      method: 'PUT',
      body: JSON.stringify(body)
    })
    console.log('[api] PUT /settings/llm ok')
    return res
  } catch (err) {
    console.error('[api] PUT /settings/llm failed', err.message)
    throw err
  }
}

async function testLlmSettingsApi(body) {
  console.log('[api] POST /settings/llm/test', { which: body.which })
  try {
    const res = await api('/settings/llm/test', {
      method: 'POST',
      body: JSON.stringify(body)
    })
    console.log('[api] POST /settings/llm/test ok', { ok: res.ok })
    return res
  } catch (err) {
    console.error('[api] POST /settings/llm/test failed', err.message)
    throw err
  }
}

// ── KB Management ─────────────────────────────────────────────
async function loadKbs() {
  try {
    kbs.value = await api('/kbs')
  } catch (err) {
    statusText.value = `Failed to load kbs: ${err.message}`
  }
}

async function loadKb(kid) {
  try {
    const kb = await api(`/kbs/${kid}`)
    currentKbName.value = kb.name || ''
    statusKb.value = `KB: ${kb.name}`
    statusText.value = 'Loading file tree...'
    const tree = await api(`/kbs/${kid}/tree`)
    fileTree.value = tree
    const files = await api(`/kbs/${kid}/files`).catch(() => [])
    fileCount.value = Array.isArray(files) ? files.length : 0
    statusText.value = 'Loading graph files...'
    try {
      const all = await api(`/kbs/${kid}/graph/files`)
      const graphFile = (all || []).find(f => f.relative_path && f.relative_path.toLowerCase() === 'graph.json')
      currentGraphFile.value = graphFile ? graphFile.relative_path : ''
    } catch (e) {
      currentGraphFile.value = ''
    }
    statusText.value = 'Loading graph...'
    await loadGraph(kid)
    statusText.value = 'Ready'
  } catch (err) {
    statusText.value = `Error: ${err.message}`
  }
}

async function loadGraph(kid) {
  graphLoading.value = true
  try {
    const queryParam = currentGraphFile.value ? `?file=${encodeURIComponent(currentGraphFile.value)}` : ''
    const data = await api(`/kbs/${kid}/graph${queryParam}`)
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
  currentGraphFile.value = ''
  statusKb.value = ''
}

async function onSelectKb(kid) {
  currentKbId.value = kid
  if (kid === null || kid === '' || kid === undefined) {
    resetView()
    return
  }
  await loadKb(kid)
}

async function openFile(relPath) {
  currentFilePath.value = relPath
  try {
    statusText.value = `Loading: ${relPath}`
    const content = await apiText(`/kbs/${currentKbId.value}/files/${encodeURIComponent(relPath)}`)
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

function toggleSidebar() {
  sidebarCollapsed.value = !sidebarCollapsed.value
  localStorage.setItem('sidebarCollapsed', sidebarCollapsed.value ? '1' : '0')
  console.log('[App] sidebar collapsed=', sidebarCollapsed.value)
}

function openChat() {
  if (!currentKbId.value) {
    alert('Please select a kb first')
    return
  }
  chatOpen.value = true
  console.log('[App] chat opened')
}

function toggleChat() {
  if (chatOpen.value) {
    chatOpen.value = false
    console.log('[App] chat closed')
    return
  }
  openChat()
}

function onNodeClick(node) {
  selectedNode.value = node
}

function onRelatedNodeClick(rel) {
  selectedNode.value = rel
}

function findNodeByTarget(target) {
  if (!graphData.value?.nodes) return null
  const normalized = target.trim().toLowerCase()
  for (const node of graphData.value.nodes) {
    if (node.id && String(node.id).toLowerCase() === normalized) return node
    if (node.label && node.label.toLowerCase() === normalized) return node
  }
  for (const node of graphData.value.nodes) {
    if (node.label && node.label.toLowerCase().includes(normalized)) return node
    if (node.path && node.path.toLowerCase().includes(normalized)) return node
  }
  return null
}

async function openWikiLink(target) {
  if (!currentKbId.value) return
  const node = findNodeByTarget(target)
  const filePath = node?.path || target
  await openFile(filePath)
}

async function onSaveFile({ filePath, content }) {
  if (!currentKbId.value) return
  statusText.value = 'Saving...'
  try {
    await api(`/kbs/${currentKbId.value}/files/${encodeURIComponent(filePath)}`, {
      method: 'PUT',
      body: JSON.stringify({ content })
    })
    statusText.value = 'File saved'
    if (currentFilePath.value === filePath) {
      const updated = await apiText(`/kbs/${currentKbId.value}/files/${encodeURIComponent(filePath)}`)
      currentFileContent.value = updated
    }
  } catch (err) {
    statusText.value = `Save failed: ${err.message}`
  }
}

async function buildKnowledgeBase() {
  if (taskRunning.value) return
  if (!currentKbId.value) return alert('Please select a kb first')
  if (!confirm('Build knowledge base? Only new raw files will be ingested.')) return

  createTask('build', 'Building Knowledge Base')
  statusText.value = 'Building knowledge base...'
  await loadKbs()

  try {
    const result = await consumeSSE(
      `/api/kbs/${currentKbId.value}/build`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ stream: true })
      },
      handleTaskEvent
    )
    finishTask(result, 'build')
    await loadKbs()
    await loadKb(currentKbId.value)
  } catch (err) {
    failTask(err)
    await loadKbs()
    alert(`Build failed: ${err.message}`)
  }
}

async function buildGraph() {
  if (taskRunning.value) return
  if (!currentKbId.value) return alert('Please select a kb first')
  statusText.value = 'Building graph...'
  try {
    const result = await api(`/kbs/${currentKbId.value}/graph/build`, { method: 'POST' })
    statusText.value = `Graph built: ${result.n_nodes} nodes, ${result.n_edges} edges`
    await loadGraph(currentKbId.value)
  } catch (err) {
    statusText.value = `Graph build failed: ${err.message}`
  }
}

async function exportKb() {
  if (!currentKbId.value) return alert('Please select a kb first')
  statusText.value = 'Exporting kb...'
  try {
    await apiDownload(
      `/kbs/${currentKbId.value}/export`,
      `${currentKbName.value}_export.zip`
    )
    statusText.value = 'Export complete'
  } catch (err) {
    statusText.value = `Export failed: ${err.message}`
    alert(`Export failed: ${err.message}`)
  }
}

function openModal(name) {
  if (!currentKbId.value && ['delete', 'import', 'lint', 'instruction'].includes(name)) {
    alert('Please select a kb first')
    return
  }
  activeModal.value = name
}

async function onKbCreated(kid) {
  await loadKbs()
  await onSelectKb(kid)
  activeModal.value = ''
}

async function onKbDeleted() {
  resetView()
  currentKbId.value = null
  await loadKbs()
  activeModal.value = ''
}

async function onImportStream(payload) {
  if (taskRunning.value) return
  activeModal.value = ''

  const { type, dirPath, formData } = payload

  if (type === 'dir') {
    createTask('import', 'Importing Files')
    statusText.value = 'Importing files...'
    try {
      const result = await consumeSSE(
        `/api/kbs/${currentKbId.value}/import`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ source_dir: dirPath, stream: true })
        },
        handleTaskEvent
      )
      finishTask(result, 'import')
      await loadKb(currentKbId.value)
    } catch (err) {
      failTask(err)
      alert(`Import failed: ${err.message}`)
    }
  } else if (type === 'zip') {
    createTask('import_zip', 'Importing ZIP')
    statusText.value = 'Importing ZIP...'
    try {
      const result = await consumeSSEUpload(
        `/api/kbs/${currentKbId.value}/import-zip?stream=true`,
        formData,
        handleTaskEvent
      )
      finishTask(result, 'import_zip')
      await loadKb(currentKbId.value)
    } catch (err) {
      failTask(err)
      alert(`Import failed: ${err.message}`)
    }
  } else if (type === 'kb') {
    createTask('import_kb', 'Importing KB')
    statusText.value = 'Importing KB...'
    try {
      const result = await consumeSSEUpload(
        '/api/kbs/import?stream=true',
        formData,
        handleTaskEvent
      )
      finishTask(result, 'import_kb')
      await loadKbs()
      if (result?.kb_id) await onSelectKb(result.kb_id)
    } catch (err) {
      failTask(err)
      alert(`Import KB failed: ${err.message}`)
    }
  }
}

onMounted(() => {
  loadKbs()
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
  gap: 8px;
  margin-left: auto;
}

.toolbar-icon-btn {
  padding: 6px 8px;
  flex-shrink: 0;
}

.toolbar-right .btn-active {
  background: rgba(0, 122, 255, 0.1);
  border-color: var(--accent);
  color: var(--accent);
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