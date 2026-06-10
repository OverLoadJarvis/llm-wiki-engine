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
            <label class="form-label">Files to import</label>
            <p style="color:var(--text-muted);font-size:12px;margin:6px 0 12px">
              Backend will scan uploaded files; drag-and-drop integration available via API.
            </p>
            <div class="import-hint hud-brackets">
              <span v-html="I.folder" style="width:14px;height:14px"></span>
              <span>Supported: .txt, .md, .json, .html, .pdf (text)</span>
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

function confirm() {
  let payload = {}
  if (props.type === 'create-project') payload = { name: name.value.trim() || 'new-project' }
  else if (props.type === 'build-knowledge-base') payload = { ...kbOptions.value }
  else if (props.type === 'build-graph') payload = { ...graphOptions.value }
  emit('confirm', payload)
}
</script>
