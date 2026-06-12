<template>
  <div>
    <!-- Create Project Modal -->
    <div v-if="active === 'create'" class="modal-overlay" @click.self="$emit('close')">
      <div class="modal">
        <h3>New Project</h3>
        <input type="text" v-model="createName" placeholder="Project name" @keydown.enter="doCreate" />
        <input type="text" v-model="createDesc" placeholder="Description (optional)" @keydown.enter="doCreate" />
        <div class="modal-actions">
          <button class="btn btn-outline" @click="$emit('close')">Cancel</button>
          <button class="btn" @click="doCreate">Create</button>
        </div>
      </div>
    </div>

    <!-- Query Modal -->
    <div v-if="active === 'query'" class="modal-overlay" @click.self="$emit('close')">
      <div class="modal" style="width:500px;">
        <h3>Query Knowledge Base</h3>
        <input type="text" v-model="queryText" placeholder="Enter your question..." @keydown.enter="doQuery" />
        <div class="query-result-area">
          <div v-if="queryLoading" class="loading">
            <div class="spinner"></div><span>Querying...</span>
          </div>
          <div v-else-if="queryError" class="query-error">{{ queryError }}</div>
          <div v-else-if="queryResult" class="query-result">{{ queryResult }}</div>
        </div>
        <div class="modal-actions">
          <button class="btn btn-outline" @click="$emit('close')">Close</button>
          <button class="btn" @click="doQuery" :disabled="queryLoading">Query</button>
        </div>
      </div>
    </div>

    <!-- Lint Modal -->
    <div v-if="active === 'lint'" class="modal-overlay" @click.self="$emit('close')">
      <div class="modal" style="width:640px;max-width:90vw;">
        <h3>Quality Check Report</h3>
        <div class="lint-result-area">
          <div v-if="lintLoading" class="loading">
            <div class="spinner"></div><span>Checking...</span>
          </div>
          <div v-else-if="lintError" class="query-error">{{ lintError }}</div>
          <div v-else-if="lintResult" v-html="renderedLintResult"></div>
        </div>
        <div class="modal-actions">
          <button class="btn btn-outline" @click="$emit('close')">Close</button>
        </div>
      </div>
    </div>

    <!-- Import Files Modal -->
    <div v-if="active === 'import'" class="modal-overlay" @click.self="$emit('close')">
      <div class="modal">
        <h3>Import Files</h3>
        <div class="import-section">
          <label>Local Directory Path</label>
          <input type="text" v-model="importDir" placeholder="e.g. D:\docs\my-project" @keydown.enter="doImport" />
        </div>
        <div class="import-section">
          <label>Or Upload ZIP Archive</label>
          <input type="file" ref="zipInput" accept=".zip" @change="onZipSelected" />
          <span v-if="zipFileName" class="file-selected">Selected: {{ zipFileName }}</span>
        </div>
        <div class="modal-actions">
          <button class="btn btn-outline" @click="$emit('close')">Cancel</button>
          <button class="btn" @click="doImport">Import</button>
        </div>
      </div>
    </div>

    <!-- Import Project Modal -->
    <div v-if="active === 'import-project'" class="modal-overlay" @click.self="$emit('close')">
      <div class="modal">
        <h3>Import Project</h3>
        <p class="modal-desc">
          Upload a project ZIP package. The file name will be used as the new project name.
        </p>
        <div class="import-section">
          <label>Select ZIP File</label>
          <input type="file" ref="projectZipInput" accept=".zip" @change="onProjectZipSelected" />
          <span v-if="projectZipFileName" class="file-selected">Selected: {{ projectZipFileName }}</span>
        </div>
        <div class="modal-actions">
          <button class="btn btn-outline" @click="$emit('close')">Cancel</button>
          <button class="btn" @click="doImportProject">Import</button>
        </div>
      </div>
    </div>

    <!-- Delete Project Confirm Modal -->
    <div v-if="active === 'delete'" class="modal-overlay" @click.self="$emit('close')">
      <div class="modal">
        <h3>Delete Project</h3>
        <p class="modal-desc">
          Are you sure you want to delete <strong class="danger-text">{{ projectName }}</strong>?
        </p>
        <p class="modal-warning">
          This action will <strong class="danger-text">permanently delete</strong> the project and all associated files. This cannot be undone.
        </p>
        <div class="modal-actions">
          <button class="btn btn-outline" @click="$emit('close')">Cancel</button>
          <button class="btn btn-danger" @click="doDelete">Delete</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'
import { renderMarkdown } from '../utils/markdown.js'

const props = defineProps({
  active: { type: String, default: '' },
  projectName: { type: String, default: '' },
  queryApi: { type: Function, required: true },
  createApi: { type: Function, required: true },
  deleteApi: { type: Function, required: true },
  importApi: { type: Function, required: true },
  importZipApi: { type: Function, required: true },
  importProjectApi: { type: Function, required: true },
  lintApi: { type: Function, required: true }
})

const emit = defineEmits(['close', 'project-created', 'project-deleted', 'files-imported', 'project-imported'])

// ── Create ────────────────────────────────────────────────────
const createName = ref('')
const createDesc = ref('')

async function doCreate() {
  if (!createName.value.trim()) return
  try {
    const result = await props.createApi({ name: createName.value.trim(), description: createDesc.value.trim() })
    emit('project-created', result.id || result)
    createName.value = ''
    createDesc.value = ''
  } catch (err) {
    alert(`Create failed: ${err.message}`)
  }
}

// ── Delete ────────────────────────────────────────────────────
async function doDelete() {
  try {
    await props.deleteApi()
    emit('project-deleted')
  } catch (err) {
    alert(`Delete failed: ${err.message}`)
  }
}

// ── Query ─────────────────────────────────────────────────────
const queryText = ref('')
const queryResult = ref('')
const queryLoading = ref(false)
const queryError = ref('')

async function doQuery() {
  if (!queryText.value.trim()) return
  queryLoading.value = true
  queryError.value = ''
  queryResult.value = ''
  try {
    const result = await props.queryApi(queryText.value.trim())
    queryResult.value = result.answer || result.response || result.result || JSON.stringify(result)
  } catch (err) {
    queryError.value = err.message
  } finally {
    queryLoading.value = false
  }
}

// ── Lint ──────────────────────────────────────────────────────
const lintResult = ref('')
const lintLoading = ref(false)
const lintError = ref('')

const renderedLintResult = ref('')

watch(() => props.active, async (val) => {
  if (val === 'lint') {
    lintLoading.value = true
    lintError.value = ''
    lintResult.value = ''
    renderedLintResult.value = ''
    try {
      const result = await props.lintApi()
      const text = result.report || result.result || JSON.stringify(result, null, 2)
      lintResult.value = text
      renderedLintResult.value = renderMarkdown(text)
    } catch (err) {
      lintError.value = err.message
    } finally {
      lintLoading.value = false
    }
  }
})

// ── Import Files ──────────────────────────────────────────────
const importDir = ref('')
const zipInput = ref(null)
const zipFileName = ref('')

function onZipSelected(e) {
  zipFileName.value = e.target.files[0]?.name || ''
}

async function doImport() {
  try {
    if (zipInput.value?.files[0]) {
      const formData = new FormData()
      formData.append('file', zipInput.value.files[0])
      await props.importZipApi(formData)
    } else if (importDir.value.trim()) {
      await props.importApi(importDir.value.trim())
    } else {
      alert('Please provide a directory path or select a ZIP file')
      return
    }
    emit('files-imported')
    importDir.value = ''
    zipFileName.value = ''
    if (zipInput.value) zipInput.value.value = ''
  } catch (err) {
    alert(`Import failed: ${err.message}`)
  }
}

// ── Import Project ────────────────────────────────────────────
const projectZipInput = ref(null)
const projectZipFileName = ref('')

function onProjectZipSelected(e) {
  projectZipFileName.value = e.target.files[0]?.name || ''
}

async function doImportProject() {
  try {
    if (!projectZipInput.value?.files[0]) {
      alert('Please select a ZIP file')
      return
    }
    const formData = new FormData()
    formData.append('file', projectZipInput.value.files[0])
    const result = await props.importProjectApi(formData)
    emit('project-imported', result.id || result)
    projectZipFileName.value = ''
    if (projectZipInput.value) projectZipInput.value.value = ''
  } catch (err) {
    alert(`Import project failed: ${err.message}`)
  }
}
</script>

<style scoped>
.modal-desc {
  font-size: 0.8125rem;
  color: var(--text-secondary);
  margin-bottom: 16px;
  line-height: 1.6;
}

.modal-warning {
  font-size: 0.8125rem;
  color: var(--text-secondary);
  margin-bottom: 16px;
  line-height: 1.6;
}

.danger-text {
  color: var(--danger);
}

.import-section {
  margin-bottom: 16px;
}

.import-section label {
  display: block;
  font-size: 0.75rem;
  font-weight: 500;
  color: var(--text-tertiary);
  margin-bottom: 6px;
  text-transform: uppercase;
  letter-spacing: 0.03em;
}

.import-section input[type="file"] {
  font-size: 0.8125rem;
  color: var(--text-secondary);
}

.file-selected {
  display: block;
  font-size: 0.75rem;
  color: var(--accent);
  margin-top: 4px;
}

.query-result-area,
.lint-result-area {
  max-height: 300px;
  overflow-y: auto;
  margin-top: 12px;
  font-size: 0.8125rem;
  line-height: 1.7;
  background: rgba(0, 0, 0, 0.02);
  border-radius: var(--radius-sm);
  padding: 14px;
}

.query-result {
  white-space: pre-wrap;
  color: var(--text-primary);
}

.query-error {
  color: var(--danger);
}

.lint-result-area :deep(h1),
.lint-result-area :deep(h2),
.lint-result-area :deep(h3) {
  font-size: 0.875rem;
  font-weight: 600;
  margin: 12px 0 6px;
}

.lint-result-area :deep(p) {
  margin: 4px 0;
}

.lint-result-area :deep(ul) {
  padding-left: 20px;
  margin: 4px 0;
}
</style>