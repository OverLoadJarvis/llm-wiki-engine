<template>
  <div>
    <!-- Create KB Modal -->
    <div v-if="active === 'create'" class="modal-overlay" @click.self="$emit('close')">
      <div class="modal">
        <h3>New KB</h3>
        <input type="text" v-model="createName" placeholder="KB name" @keydown.enter="doCreate" />
        <input type="text" v-model="createDesc" placeholder="Description (optional)" @keydown.enter="doCreate" />
        <div class="modal-actions">
          <button class="btn btn-outline" @click="$emit('close')">Cancel</button>
          <button class="btn" @click="doCreate">Create</button>
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
          <button class="btn btn-outline" @click="$emit('close')" :disabled="importLoading">Cancel</button>
          <button class="btn" @click="doImport" :disabled="importLoading || taskRunning">
            <span v-if="importLoading" class="spinner"></span>
            {{ importLoading ? 'Importing...' : 'Import' }}
          </button>
        </div>
      </div>
    </div>

    <!-- Import KB Modal -->
    <div v-if="active === 'import-kb'" class="modal-overlay" @click.self="$emit('close')">
      <div class="modal">
        <h3>Import KB</h3>
        <p class="modal-desc">
          Upload a KB ZIP package. The file name will be used as the new KB name.
        </p>
        <div class="import-section">
          <label>Select ZIP File</label>
          <input type="file" ref="kbZipInput" accept=".zip" @change="onKbZipSelected" />
          <span v-if="kbZipFileName" class="file-selected">Selected: {{ kbZipFileName }}</span>
        </div>
        <div class="modal-actions">
          <button class="btn btn-outline" @click="$emit('close')" :disabled="importLoading">Cancel</button>
          <button class="btn" @click="doImportKb" :disabled="importLoading || taskRunning">
            <span v-if="importLoading" class="spinner"></span>
            {{ importLoading ? 'Importing...' : 'Import' }}
          </button>
        </div>
      </div>
    </div>

    <!-- Delete KB Confirm Modal -->
    <div v-if="active === 'delete'" class="modal-overlay" @click.self="$emit('close')">
      <div class="modal">
        <h3>Delete KB</h3>
        <p class="modal-desc">
          Are you sure you want to delete <strong class="danger-text">{{ kbName }}</strong>?
        </p>
        <p class="modal-warning">
          This action will <strong class="danger-text">permanently delete</strong> the KB and all associated files. This cannot be undone.
        </p>
        <div class="modal-actions">
          <button class="btn btn-outline" @click="$emit('close')">Cancel</button>
          <button class="btn btn-danger" @click="doDelete">Delete</button>
        </div>
      </div>
    </div>

    <!-- Instruction Modal -->
    <div v-if="active === 'instruction'" class="modal-overlay" @click.self="$emit('close')">
      <div class="modal" style="width:520px;">
        <h3>Build Instructions</h3>
        <p class="modal-desc">
          These instructions will be appended to the prompt when building or updating the knowledge base.
          The LLM will use them to guide the ingestion process.
        </p>
        <textarea class="instruction-textarea" v-model="instructionText" placeholder="e.g. Focus on technical details, extract all API endpoints, ignore marketing content..."></textarea>
        <div class="modal-actions">
          <button class="btn btn-outline" @click="$emit('close')">Cancel</button>
          <button class="btn" @click="doSaveInstruction">Save</button>
        </div>
      </div>
    </div>

    <!-- LLM Settings Modal -->
    <div v-if="active === 'llm-settings'" class="modal-overlay" @click.self="$emit('close')">
      <div class="modal" style="width:520px;">
        <h3>LLM Settings</h3>
        <p class="modal-desc">
          Global configuration for all knowledge bases. Saved values override environment variables.
          Leave API Key blank to keep the existing key.
        </p>
        <div v-if="llmLoading" class="loading">
          <div class="spinner"></div><span>Loading...</span>
        </div>
        <template v-else>
          <div class="import-section">
            <label>Base URL</label>
            <input
              type="text"
              v-model="llmForm.base_url"
              :placeholder="llmResolved.base_url || 'https://api.openai.com/v1'"
            />
          </div>
          <div class="import-section">
            <label>API Key</label>
            <input
              type="password"
              v-model="llmForm.api_key"
              :placeholder="llmApiKeyPlaceholder"
              autocomplete="off"
            />
          </div>
          <div class="import-section">
            <label>Model (default)</label>
            <input
              type="text"
              v-model="llmForm.model"
              :placeholder="llmResolved.model || 'model name'"
            />
          </div>
          <div class="import-section">
            <label>Fast Model</label>
            <input
              type="text"
              v-model="llmForm.model_fast"
              :placeholder="llmResolved.model_fast || 'fast model name'"
            />
          </div>
          <div
            v-if="llmTestMessage || llmTesting"
            class="llm-test-result"
            :class="{
              ok: llmTestOk && !llmTesting,
              err: !llmTestOk && !llmTesting,
              pending: !!llmTesting
            }"
          >
            {{ llmTestMessage }}
          </div>
          <div class="modal-actions llm-actions">
            <button type="button" class="btn btn-outline" @click="doTestLlm('model')" :disabled="!!llmTesting">
              {{ llmTesting === 'model' ? 'Testing...' : 'Test Model' }}
            </button>
            <button type="button" class="btn btn-outline" @click="doTestLlm('model_fast')" :disabled="!!llmTesting">
              {{ llmTesting === 'model_fast' ? 'Testing...' : 'Test Fast' }}
            </button>
            <span class="llm-actions-spacer"></span>
            <button type="button" class="btn btn-outline" @click="$emit('close')" :disabled="!!llmTesting || llmSaving">Cancel</button>
            <button type="button" class="btn" @click="doSaveLlm" :disabled="!!llmTesting || llmSaving">
              {{ llmSaving ? 'Saving...' : 'Save' }}
            </button>
          </div>
        </template>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, computed } from 'vue'
import { renderMarkdown } from '../utils/markdown.js'

const props = defineProps({
  active: { type: String, default: '' },
  kbName: { type: String, default: '' },
  taskRunning: { type: Boolean, default: false },
  createApi: { type: Function, required: true },
  deleteApi: { type: Function, required: true },
  lintApi: { type: Function, required: true },
  instructionApi: { type: Function, required: true },
  setInstructionApi: { type: Function, required: true },
  getLlmSettingsApi: { type: Function, required: true },
  setLlmSettingsApi: { type: Function, required: true },
  testLlmSettingsApi: { type: Function, required: true }
})

const emit = defineEmits(['close', 'kb-created', 'kb-deleted', 'import-stream'])

// ── Create ────────────────────────────────────────────────────
const createName = ref('')
const createDesc = ref('')

async function doCreate() {
  if (!createName.value.trim()) return
  try {
    const result = await props.createApi({ name: createName.value.trim(), description: createDesc.value.trim() })
    emit('kb-created', result.id || result)
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
    emit('kb-deleted')
  } catch (err) {
    alert(`Delete failed: ${err.message}`)
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
const importLoading = ref(false)

function onZipSelected(e) {
  zipFileName.value = e.target.files[0]?.name || ''
}

async function doImport() {
  if (props.taskRunning || importLoading.value) return
  try {
    if (zipInput.value?.files[0]) {
      const formData = new FormData()
      formData.append('file', zipInput.value.files[0])
      importLoading.value = true
      emit('import-stream', { type: 'zip', formData })
      importDir.value = ''
      zipFileName.value = ''
      if (zipInput.value) zipInput.value.value = ''
    } else if (importDir.value.trim()) {
      importLoading.value = true
      emit('import-stream', { type: 'dir', dirPath: importDir.value.trim() })
      importDir.value = ''
    } else {
      alert('Please provide a directory path or select a ZIP file')
      return
    }
  } catch (err) {
    alert(`Import failed: ${err.message}`)
  } finally {
    importLoading.value = false
  }
}

// ── Import KB ─────────────────────────────────────────────────
const kbZipInput = ref(null)
const kbZipFileName = ref('')

function onKbZipSelected(e) {
  kbZipFileName.value = e.target.files[0]?.name || ''
}

async function doImportKb() {
  if (props.taskRunning || importLoading.value) return
  try {
    if (!kbZipInput.value?.files[0]) {
      alert('Please select a ZIP file')
      return
    }
    const formData = new FormData()
    formData.append('file', kbZipInput.value.files[0])
    importLoading.value = true
    emit('import-stream', { type: 'kb', formData })
    kbZipFileName.value = ''
    if (kbZipInput.value) kbZipInput.value.value = ''
  } catch (err) {
    alert(`Import kb failed: ${err.message}`)
  } finally {
    importLoading.value = false
  }
}

// ── Instruction ───────────────────────────────────────────────
const instructionText = ref('')

watch(() => props.active, async (val) => {
  if (val === 'instruction') {
    instructionText.value = ''
    try {
      const result = await props.instructionApi()
      instructionText.value = result.instruction || ''
    } catch (err) {
      console.error('Failed to load instruction:', err)
    }
  }
})

async function doSaveInstruction() {
  try {
    await props.setInstructionApi(instructionText.value)
    emit('close')
  } catch (err) {
    alert(`Save failed: ${err.message}`)
  }
}

// ── LLM Settings ──────────────────────────────────────────────
const llmLoading = ref(false)
const llmSaving = ref(false)
const llmTesting = ref('')
const llmApiKeySet = ref(false)
const llmApiKeyMasked = ref('')
const llmForm = ref({
  base_url: '',
  api_key: '',
  model: '',
  model_fast: ''
})
const llmResolved = ref({
  base_url: '',
  model: '',
  model_fast: ''
})
const llmTestOk = ref(false)
const llmTestMessage = ref('')

const llmApiKeyPlaceholder = computed(() => {
  if (llmApiKeySet.value && llmApiKeyMasked.value) {
    return `Configured (${llmApiKeyMasked.value}), leave blank to keep`
  }
  if (llmApiKeySet.value) {
    return 'Configured, leave blank to keep'
  }
  return 'API key'
})

watch(() => props.active, async (val) => {
  if (val === 'llm-settings') {
    llmLoading.value = true
    llmTestMessage.value = ''
    llmForm.value = { base_url: '', api_key: '', model: '', model_fast: '' }
    try {
      console.log('[LLMSettings] GET /settings/llm')
      const data = await props.getLlmSettingsApi()
      llmForm.value = {
        base_url: data.base_url || '',
        api_key: '',
        model: data.model || '',
        model_fast: data.model_fast || ''
      }
      llmApiKeySet.value = !!data.api_key_set
      llmApiKeyMasked.value = data.api_key_masked || ''
      llmResolved.value = {
        base_url: data.resolved_base_url || '',
        model: data.resolved_model || '',
        model_fast: data.resolved_model_fast || ''
      }
      console.log('[LLMSettings] GET ok', {
        api_key_set: llmApiKeySet.value,
        model: llmForm.value.model,
        model_fast: llmForm.value.model_fast
      })
    } catch (err) {
      console.error('[LLMSettings] GET failed', err.message)
      alert(`Load LLM settings failed: ${err.message}`)
    } finally {
      llmLoading.value = false
    }
  }
})

async function doSaveLlm() {
  llmSaving.value = true
  llmTestMessage.value = ''
  try {
    const body = {
      base_url: llmForm.value.base_url.trim(),
      model: llmForm.value.model.trim(),
      model_fast: llmForm.value.model_fast.trim()
    }
    if (llmForm.value.api_key) {
      body.api_key = llmForm.value.api_key
    }
    console.log('[LLMSettings] PUT /settings/llm', {
      base_url: body.base_url,
      model: body.model,
      model_fast: body.model_fast,
      api_key_provided: !!body.api_key
    })
    const data = await props.setLlmSettingsApi(body)
    llmApiKeySet.value = !!data.api_key_set
    llmApiKeyMasked.value = data.api_key_masked || ''
    llmForm.value.api_key = ''
    console.log('[LLMSettings] PUT ok')
    emit('close')
  } catch (err) {
    console.error('[LLMSettings] PUT failed', err.message)
    alert(`Save failed: ${err.message}`)
  } finally {
    llmSaving.value = false
  }
}

async function doTestLlm(which) {
  llmTesting.value = which
  llmTestOk.value = false
  llmTestMessage.value = which === 'model_fast'
    ? 'Testing fast model connection...'
    : 'Testing model connection...'
  try {
    const body = {
      base_url: llmForm.value.base_url.trim(),
      model: llmForm.value.model.trim(),
      model_fast: llmForm.value.model_fast.trim(),
      which
    }
    if (llmForm.value.api_key) {
      body.api_key = llmForm.value.api_key
    }
    console.log('[LLMSettings] POST /settings/llm/test', { which, model: which === 'model_fast' ? body.model_fast : body.model })
    const result = await props.testLlmSettingsApi(body)
    if (result.ok) {
      llmTestOk.value = true
      llmTestMessage.value = `Connection successful — ${result.model} (${result.latency_ms} ms)`
      console.log('[LLMSettings] test ok', result)
    } else {
      llmTestOk.value = false
      llmTestMessage.value = `Connection failed: ${result.error || 'Unknown error'}`
      console.warn('[LLMSettings] test failed', result.error)
    }
  } catch (err) {
    llmTestOk.value = false
    llmTestMessage.value = `Connection failed: ${err.message}`
    console.error('[LLMSettings] test error', err.message)
  } finally {
    llmTesting.value = ''
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

.instruction-textarea {
  width: 100%;
  height: 200px;
  font-family: var(--font-sans);
  font-size: 0.8125rem;
  line-height: 1.6;
  padding: 12px;
  border: 1px solid rgba(0, 0, 0, 0.12);
  border-radius: var(--radius-sm);
  resize: vertical;
  outline: none;
  transition: border-color var(--transition-fast);
  box-sizing: border-box;
  margin-bottom: 16px;
}

.instruction-textarea:focus {
  border-color: var(--accent);
}

.llm-actions {
  flex-wrap: wrap;
  gap: 8px;
}

.llm-actions-spacer {
  flex: 1;
  min-width: 8px;
}

.llm-test-result {
  font-size: 0.8125rem;
  margin-bottom: 12px;
  padding: 8px 12px;
  border-radius: var(--radius-sm);
  line-height: 1.5;
  word-break: break-word;
}

.llm-test-result.pending {
  color: var(--text-secondary);
  background: rgba(0, 0, 0, 0.04);
}

.llm-test-result.ok {
  color: #1a7f37;
  background: rgba(26, 127, 55, 0.08);
}

.llm-test-result.err {
  color: var(--danger);
  background: rgba(255, 59, 48, 0.08);
}
</style>