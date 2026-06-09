<template>
  <div>
    <!-- Create Project Modal -->
    <div v-if="active === 'create'" class="modal-overlay" @click.self="$emit('close')">
      <div class="modal">
        <h3>新建项目</h3>
        <input type="text" v-model="createName" placeholder="项目名称" @keydown.enter="doCreate" />
        <input type="text" v-model="createDesc" placeholder="描述（可选）" @keydown.enter="doCreate" />
        <div class="modal-actions">
          <button class="btn btn-outline" @click="$emit('close')">取消</button>
          <button class="btn" @click="doCreate">创建</button>
        </div>
      </div>
    </div>

    <!-- Query Modal -->
    <div v-if="active === 'query'" class="modal-overlay" style="" @click.self="$emit('close')">
      <div class="modal" style="width:500px;">
        <h3>查询知识库</h3>
        <input type="text" v-model="queryText" placeholder="输入你的问题..." @keydown.enter="doQuery" />
        <div style="max-height:300px;overflow-y:auto;margin-top:12px;font-size:13px;line-height:1.6;white-space:pre-wrap;">
          <div v-if="queryLoading" class="loading"><div class="spinner"></div><span>查询中...</span></div>
          <div v-else-if="queryError" style="color:var(--danger);">{{ queryError }}</div>
          <div v-else-if="queryResult">{{ queryResult }}</div>
        </div>
        <div class="modal-actions">
          <button class="btn btn-outline" @click="$emit('close')">关闭</button>
          <button class="btn" @click="doQuery" :disabled="queryLoading">查询</button>
        </div>
      </div>
    </div>

    <!-- Lint Modal -->
    <div v-if="active === 'lint'" class="modal-overlay" @click.self="$emit('close')">
      <div class="modal" style="width:640px;max-width:90vw;">
        <h3>质量检查报告</h3>
        <div style="max-height:500px;overflow-y:auto;margin-top:12px;font-size:13px;line-height:1.7;">
          <div v-if="lintLoading" class="loading"><div class="spinner"></div><span>检查中...</span></div>
          <div v-else-if="lintError" style="color:var(--danger);">{{ lintError }}</div>
          <div v-else-if="lintResult" v-html="renderedLintResult"></div>
        </div>
        <div class="modal-actions">
          <button class="btn btn-outline" @click="$emit('close')">关闭</button>
        </div>
      </div>
    </div>

    <!-- Import Files Modal -->
    <div v-if="active === 'import'" class="modal-overlay" @click.self="$emit('close')">
      <div class="modal">
        <h3>导入文件</h3>
        <input type="text" v-model="importDir" placeholder="本地目录路径" @keydown.enter="doImport" />
        <div class="modal-actions">
          <button class="btn btn-outline" @click="$emit('close')">取消</button>
          <button class="btn" @click="doImport">导入</button>
        </div>
      </div>
    </div>

    <!-- Delete Project Confirm Modal -->
    <div v-if="active === 'delete'" class="modal-overlay" @click.self="$emit('close')">
      <div class="modal">
        <h3>删除项目</h3>
        <p style="color:var(--text-dim);margin-bottom:16px;line-height:1.6;">
          确定要删除项目 <strong style="color:var(--danger);">{{ projectName }}</strong> 吗？<br/>
          此操作将<strong style="color:var(--danger);">永久删除</strong>该项目及其所有关联文件，不可恢复。
        </p>
        <div class="modal-actions">
          <button class="btn btn-outline" @click="$emit('close')">取消</button>
          <button class="btn" style="background:var(--danger);" @click="doDelete">确认删除</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { renderMarkdown } from '../utils/markdown.js'

const props = defineProps({
  active: { type: String, default: '' },
  projectName: { type: String, default: '—' },
  queryApi: { type: Function, default: null },
  createApi: { type: Function, default: null },
  deleteApi: { type: Function, default: null },
  importApi: { type: Function, default: null },
  lintApi: { type: Function, default: null }
})

const emit = defineEmits(['close', 'project-created', 'project-deleted', 'files-imported'])

const createName = ref('')
const createDesc = ref('')
const queryText = ref('')
const queryResult = ref('')
const queryError = ref('')
const queryLoading = ref(false)

const lintResult = ref('')
const lintError = ref('')
const lintLoading = ref(false)

const importDir = ref('')

const renderedLintResult = computed(() => lintResult.value ? renderMarkdown(lintResult.value) : '')

async function doCreate() {
  const name = createName.value.trim()
  if (!name) return alert('请输入项目名称')
  try {
    const result = await props.createApi({ name, description: createDesc.value.trim() })
    emit('project-created', result)
    createName.value = ''
    createDesc.value = ''
  } catch (err) {
    alert(`创建失败: ${err.message}`)
  }
}

async function doQuery() {
  const q = queryText.value.trim()
  if (!q) return
  queryLoading.value = true
  queryError.value = ''
  queryResult.value = ''
  try {
    const result = await props.queryApi(q)
    queryResult.value = result.answer
  } catch (err) {
    queryError.value = `查询失败: ${err.message}`
  } finally {
    queryLoading.value = false
  }
}

async function doImport() {
  const dir = importDir.value.trim()
  if (!dir) return alert('请输入目录路径')
  try {
    const result = await props.importApi(dir)
    emit('files-imported', result)
    importDir.value = ''
  } catch (err) {
    alert(`导入失败: ${err.message}`)
  }
}

async function doDelete() {
  try {
    await props.deleteApi()
    emit('project-deleted')
  } catch (err) {
    alert(`删除失败: ${err.message}`)
  }
}

watch(() => props.active, (newVal) => {
  if (newVal === 'lint' && props.lintApi) {
    lintLoading.value = true
    lintError.value = ''
    lintResult.value = ''
    props.lintApi().then(r => {
      lintResult.value = r.report
      lintLoading.value = false
    }).catch(err => {
      lintError.value = err.message
      lintLoading.value = false
    })
  }
})
</script>
