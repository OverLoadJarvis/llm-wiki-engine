<template>
  <div style="height:100vh;display:flex;flex-direction:column;">
    <Topbar
      :projects="projects"
      :selected-project-id="currentProjectId"
      @select-project="onSelectProject"
      @create-project="openModal('create')"
      @delete-project="openModal('delete')"
      @import-files="openModal('import')"
      @build-knowledge-base="buildKnowledgeBase"
      @build-graph="buildGraph"
      @lint-project="openModal('lint')"
      @export-project="exportProject"
      @show-query="openModal('query')"
    />

    <div class="main-layout">
      <Sidebar
      v-if="currentProjectId"
      :tree="fileTree"
      :file-count="fileCount"
      :active-path="currentFilePath"
      @select-file="openFile"
    />

      <div class="content-area" style="flex:1;display:flex;flex-direction:column;overflow:hidden;">
        <div class="content-toolbar">
          <span class="title" v-if="currentView === 'graph'">知识图谱</span>
          <span class="title" v-else>{{ currentFilePath }}</span>
          <span class="badge">{{ currentProjectName }}</span>
          <div v-if="currentView === 'graph' && graphFilesList.length > 0" class="graph-file-selector">
            <select :value="currentGraphFile" @change="onGraphFileChange">
              <option v-for="f in graphFilesList" :key="f.relative_path" :value="f.relative_path">{{ f.file_name }}</option>
            </select>
          </div>
          <div v-if="currentView === 'graph'" class="confidence-control">
            <span class="confidence-label">置信度</span>
            <input type="range" min="0" max="1" step="0.05"
                   :value="confidence"
                   @input="confidence = parseFloat($event.target.value)" />
            <span class="confidence-value">{{ confidence.toFixed(2) }}</span>
          </div>
          <div style="flex:1"></div>
          <button class="btn btn-sm btn-outline" @click="toggleView">
            {{ currentView === 'graph' ? '文件视图' : '图谱视图' }}
          </button>
        </div>

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
          <div v-else class="file-view">
            <div class="empty-state" style="padding:40px 16px;">
              <p>请从左侧选择文件</p>
            </div>
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

    <StatusBar :status-text="statusText" :status-project="statusProject" />

    <ChatPanel
      :current-project-id="currentProjectId"
      :query-api="queryApi"
    />

    <ModalGroup
      :active="activeModal"
      :project-name="currentProjectName"
      :query-api="queryApi"
      :create-api="createProjectApi"
      :delete-api="deleteProjectApi"
      :import-api="importFilesApi"
      :import-zip-api="importZipApi"
      :lint-api="lintProjectApi"
      @close="activeModal = ''"
      @project-created="onProjectCreated"
      @project-deleted="onProjectDeleted"
      @files-imported="onFilesImported"
    />
  </div>
</template>

<script setup>
import { ref, computed, onMounted, provide } from 'vue'
import Topbar from './components/Topbar.vue'
import Sidebar from './components/Sidebar.vue'
import GraphView from './components/GraphView.vue'
import FileView from './components/FileView.vue'
import DetailPanel from './components/DetailPanel.vue'
import ChatPanel from './components/ChatPanel.vue'
import ModalGroup from './components/ModalGroup.vue'
import StatusBar from './components/StatusBar.vue'
import { api, apiText, apiUpload, apiDownload } from './utils/api.js'

// State
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
const statusText = ref('就绪')
const statusProject = ref('')
const activeModal = ref('')
const selectedNode = ref(null)
const graphViewRef = ref(null)

const graphAdjacencyMap = computed(() => graphViewRef.value?.adjacencyMap || new Map())
const graphNodeIndex = computed(() => graphViewRef.value?.nodeIndex || new Map())

// Load projects
async function loadProjects() {
  try {
    projects.value = await api('/projects')
  } catch (err) {
    statusText.value = `加载项目失败: ${err.message}`
  }
}

async function loadProject(pid) {
  try {
    const proj = await api(`/projects/${pid}`)
    currentProjectName.value = proj.name || ''
    statusProject.value = `项目: ${proj.name}`
    statusText.value = '加载文件树...'
    // Load tree
    const tree = await api(`/projects/${pid}/tree`)
    fileTree.value = tree
    const files = await api(`/projects/${pid}/files`).catch(() => [])
    fileCount.value = Array.isArray(files) ? files.length : 0
    // Load graph files
    statusText.value = '加载图谱文件列表...'
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
    // Load graph
    statusText.value = '加载图谱...'
    await loadGraph(pid)
    statusText.value = '就绪'
  } catch (err) {
    statusText.value = `错误: ${err.message}`
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
    statusText.value = `加载: ${relPath}`
    const content = await apiText(`/projects/${currentProjectId.value}/files/${encodeURIComponent(relPath)}`)
    currentFileContent.value = content
    currentView.value = 'file'
    statusText.value = `已打开: ${relPath}`
  } catch (err) {
    statusText.value = `加载失败: ${err.message}`
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

async function buildKnowledgeBase() {
  if (!currentProjectId.value) return alert('请先选择项目')
  if (!confirm('确定要构建知识库吗？这可能需要较长时间。')) return
  statusText.value = '正在构建知识库...'
  try {
    const result = await api(`/projects/${currentProjectId.value}/build`, {
      method: 'POST'
    })
    statusText.value = `构建完成: 摄入 ${result.ingested} 个文件`
    await loadProject(currentProjectId.value)
  } catch (err) {
    statusText.value = `构建失败: ${err.message}`
    alert(`构建失败: ${err.message}`)
  }
}

async function buildGraph() {
  if (!currentProjectId.value) return alert('请先选择项目')
  statusText.value = '正在构建图谱...'
  try {
    const result = await api(`/projects/${currentProjectId.value}/graph/build`, {
      method: 'POST'
    })
    statusText.value = `图谱构建完成: ${result.n_nodes} 节点, ${result.n_edges} 边`
    await loadGraph(currentProjectId.value)
  } catch (err) {
    statusText.value = `图谱构建失败: ${err.message}`
  }
}

async function exportProject() {
  if (!currentProjectId.value) return alert('请先选择项目')
  statusText.value = '正在导出项目...'
  try {
    await apiDownload(
      `/projects/${currentProjectId.value}/export`,
      `${currentProjectName.value}_export.zip`
    )
    statusText.value = '导出完成'
  } catch (err) {
    statusText.value = `导出失败: ${err.message}`
    alert(`导出失败: ${err.message}`)
  }
}

function openModal(kind) {
  if ((kind === 'query' || kind === 'delete' || kind === 'import') && !currentProjectId.value) {
    alert('请先选择项目')
    return
  }
  activeModal.value = kind
}

function openWikiLink(target) {
  const allPaths = Object.keys(fileTree.value || {})
  // recursively collect all file paths and find matching
  const match = allPaths.find(p => p.toLowerCase().includes(target.toLowerCase()))
  if (match) openFile(match)
  else statusText.value = `未找到链接目标: ${target}`
}

// API wrappers for modals
function queryApi(question) {
  return api(`/projects/${currentProjectId.value}/query`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question })
  })
}

function createProjectApi({ name, description }) {
  return api('/projects', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, description })
  })
}

function deleteProjectApi() {
  return api(`/projects/${currentProjectId.value}`, { method: 'DELETE' })
}

function importFilesApi(sourceDir) {
  return api(`/projects/${currentProjectId.value}/import`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ source_dir: sourceDir })
  })
}

function importZipApi(zipFile) {
  const formData = new FormData()
  formData.append('file', zipFile)
  return apiUpload(`/projects/${currentProjectId.value}/import-zip`, formData)
}

function lintProjectApi() {
  return api(`/projects/${currentProjectId.value}/lint`, { method: 'POST' })
}

async function onProjectCreated(result) {
  activeModal.value = ''
  await loadProjects()
  currentProjectId.value = result.id
  await loadProject(result.id)
}

async function onProjectDeleted() {
  activeModal.value = ''
  currentProjectId.value = null
  resetView()
  await loadProjects()
  statusText.value = '项目已删除'
}

async function onFilesImported(result) {
  activeModal.value = ''
  statusText.value = `导入完成: ${result.imported} 个文件`
  await loadProject(currentProjectId.value)
}

onMounted(async () => {
  await loadProjects()
})
</script>
