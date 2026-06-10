<template>
  <transition name="modal">
    <div v-if="show" class="modal-backdrop" @click.self="$emit('close')">
      <div class="modal">
        <div class="modal-header">
          <div>
            <div class="uppercase-label" style="color:var(--neon-cyan)">ACTION</div>
            <div class="modal-title">{{ title }}</div>
          </div>
          <button class="btn btn-sm btn-ghost" @click="$emit('close')">
            <span v-html="I.x" style="width:14px;height:14px"></span>
          </button>
        </div>

        <div class="modal-body">
          <div v-if="type === 'create-project'">
            <label class="form-label">Project name</label>
            <input type="text" v-model="name" class="form-input" placeholder="my-project" />
          </div>

          <div v-else-if="type === 'delete-project'">
            <p style="color:var(--status-error);margin:0">
              Are you sure you want to delete project <strong>{{ projectName || 'current' }}</strong>? This cannot be undone.
            </p>
          </div>

          <div v-else-if="type === 'build-knowledge-base'" class="build-options">
            <label class="form-label">Build options</label>
            <label class="form-check">
              <input type="checkbox" v-model="kbOptions.rebuild" />
              <span>Rebuild from scratch</span>
            </label>
            <label class="form-check">
              <input type="checkbox" v-model="kbOptions.incremental" />
              <span>Incremental update</span>
            </label>
          </div>

          <div v-else-if="type === 'build-graph'" class="build-options">
            <label class="form-label">Graph options</label>
            <label class="form-check">
              <input type="checkbox" v-model="graphOptions.rebuild" />
              <span>Rebuild graph</span>
            </label>
            <label class="form-check">
              <input type="checkbox" v-model="graphOptions.includeEntities" />
              <span>Include entities</span>
            </label>
            <label class="form-check">
              <input type="checkbox" v-model="graphOptions.includeConcepts" />
              <span>Include concepts</span>
            </label>
          </div>

          <div v-else-if="type === 'import-files'">
            <label class="form-label">Import source</label>
            <div style="margin-bottom:12px;">
              <label style="display:block;font-size:12px;color:var(--text-muted);margin-bottom:4px;">Local directory path</label>
              <input type="text" v-model="importDir" class="form-input" placeholder="e.g. /home/docs/project" @keydown.enter="confirm" />
            </div>
            <div style="margin-bottom:12px;">
              <label style="display:block;font-size:12px;color:var(--text-muted);margin-bottom:4px;">Or upload a ZIP archive</label>
              <input type="file" ref="zipInput" accept=".zip" @change="onZipSelected" style="display:block;width:100%;font-size:13px;color:var(--text-primary);" />
              <span v-if="zipFileName" style="display:block;font-size:11px;color:var(--text-muted);margin-top:4px;">Selected: {{ zipFileName }}</span>
            </div>
          </div>

          <div v-else-if="type === 'lint-report'" class="lint-list">
            <div v-if="lintResult.length === 0" class="empty-state">
              <span v-html="I.shield" style="width:36px;height:36px;color:var(--status-ok)"></span>
              <p>No issues found</p>
            </div>
            <div v-for="(it, i) in lintResult" :key="i" class="lint-row" :class="it.severity">
              <span class="lint-chip">{{ it.severity }}</span>
              <span class="lint-path">{{ it.path }}</span>
              <span class="lint-msg">{{ it.message }}</span>
            </div>
          </div>

          <div v-else-if="type === 'confirm'" style="color:var(--text-muted)">
            <p>{{ message }}</p>
          </div>
        </div>

        <div class="modal-footer">
          <button class="btn btn-ghost" @click="$emit('close')">Cancel</button>
          <button class="btn" :class="type === 'delete-project' ? 'btn-danger' : 'btn-primary'" @click="confirm">
            {{ confirmText }}
          </button>
        </div>
      </div>
    </div>
  </transition>
</template>

<script setup>
import { ref, watch } from 'vue'
import { I } from '../utils/icons.js'

const props = defineProps({
  show: { type: Boolean, default: false },
  type: { type: String, default: 'confirm' },
  title: { type: String, default: 'Confirm' },
  message: { type: String, default: '' },
  projectName: { type: String, default: '' },
  lintResult: { type: Array, default: () => [] }
})
const emit = defineEmits(['close', 'confirm'])

const name = ref('')
const kbOptions = ref({ rebuild: false, incremental: true })
const graphOptions = ref({ rebuild: false, includeEntities: true, includeConcepts: true })
const importDir = ref('')
const zipInput = ref(null)
const zipFileName = ref('')

const confirmText = ref('OK')

watch([() => props.type, () => props.show], () => {
  const map = {
    'create-project': 'Create',
    'delete-project': 'Delete',
    'build-knowledge-base': 'Start build',
    'build-graph': 'Build graph',
    'import-files': 'Import',
    'lint-report': 'Close',
    'confirm': 'Confirm'
  }
  confirmText.value = map[props.type] || 'OK'
})

function onZipSelected(e) {
  const file = e.target.files[0]
  zipFileName.value = file ? file.name : ''
}

function confirm() {
  let payload = {}
  if (props.type === 'create-project') payload = { name: name.value.trim() || 'new-project' }
  else if (props.type === 'build-knowledge-base') payload = { ...kbOptions.value }
  else if (props.type === 'build-graph') payload = { ...graphOptions.value }
  else if (props.type === 'import-files') {
    const zipFile = zipInput.value?.files[0]
    payload = {
      sourceDir: importDir.value.trim(),
      zipFile: zipFile || null
    }
  }
  emit('confirm', payload)
}
</script>
