<template>
  <div class="sidebar" :class="{ collapsed: sidebarCollapsed }">
    <div class="sidebar-header hud-brackets">
      <div>
        <div class="sidebar-section-title">File System</div>
        <div style="font-family:var(--font-display);font-size:13px;color:var(--text-primary);margin-top:4px">
          {{ projectName || 'No project' }}
        </div>
      </div>
      <span class="chip">{{ fileCount }} files</span>
    </div>

    <div class="sidebar-search">
      <div class="search-wrap">
        <span v-html="I.search" style="width:16px;height:16px;color:var(--text-muted)"></span>
        <input type="text" v-model="searchQuery" placeholder="search path..." />
      </div>
    </div>

    <div class="tree-container">
      <div v-if="!hasTree" class="empty-state" style="padding:30px 16px;height:auto">
        <span v-html="I.folder" style="width:40px;height:40px;color:var(--text-muted)"></span>
        <p>Select a project to browse files</p>
      </div>
      <div v-else-if="Object.keys(visibleTree).length === 0" class="empty-state" style="padding:30px 16px;height:auto">
        <span v-html="I.search" style="width:40px;height:40px;color:var(--text-muted)"></span>
        <p>No files match "{{ searchQuery }}"</p>
      </div>
      <div v-else>
        <TreeNode
          v-for="(child, key) in visibleTree"
          :key="key"
          :node="child"
          :name="key"
          :path="key"
          :active-path="activePath"
          :collapsed-paths="collapsedPaths"
          @toggle="togglePath"
          @select="handleSelect"
        />
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, h, defineComponent } from 'vue'
import { getFileType } from '../utils/api.js'
import { I, iconForFileType } from '../utils/icons.js'

const props = defineProps({
  tree: { type: Object, default: null },
  fileCount: { type: Number, default: 0 },
  activePath: { type: String, default: '' },
  projectName: { type: String, default: '' }
})

const emit = defineEmits(['select-file'])

const searchQuery = ref('')
const collapsedPaths = ref(new Set())
const sidebarCollapsed = ref(false)

const hasTree = computed(() => !!props.tree && Object.keys(props.tree).length > 0)

function filterTree(node, query, path) {
  if (typeof node === 'object' && node !== null && !Array.isArray(node)) {
    const result = {}
    let any = false
    for (const [key, child] of Object.entries(node)) {
      const childPath = path ? `${path}/${key}` : key
      const filtered = filterTree(child, query, childPath)
      if (filtered !== null) {
        result[key] = filtered
        any = true
      }
    }
    return any ? result : null
  }
  return path.toLowerCase().includes(query) ? node : null
}

const visibleTree = computed(() => {
  if (!props.tree) return {}
  const q = searchQuery.value.trim().toLowerCase()
  if (!q) return props.tree
  return filterTree(props.tree, q, '') || {}
})

function togglePath(path) {
  const next = new Set(collapsedPaths.value)
  if (next.has(path)) next.delete(path)
  else next.add(path)
  collapsedPaths.value = next
}

function handleSelect(path) {
  emit('select-file', path)
}

// TreeNode recursive render component
const TreeNode = defineComponent({
  name: 'TreeNode',
  props: {
    node: { type: [Object, Array, Number, String, Boolean], required: true },
    name: { type: String, required: true },
    path: { type: String, required: true },
    activePath: { type: String, default: '' },
    collapsedPaths: { type: Set, default: () => new Set() }
  },
  emits: ['toggle', 'select'],
  setup(props, { emit }) {
    const isDir = computed(() =>
      typeof props.node === 'object' && props.node !== null && !Array.isArray(props.node)
    )
    const isCollapsed = computed(() => props.collapsedPaths.has(props.path))
    const type = computed(() => (isDir.value ? 'folder' : getFileType(props.path)))
    const isActive = computed(() => props.activePath === props.path)

    return () => {
      const children = []
      if (isDir.value && !isCollapsed.value) {
        const entries = Object.entries(props.node)
        entries.sort(([a, aData], [b, bData]) => {
          const aDir = typeof aData === 'object' && aData !== null && !Array.isArray(aData)
          const bDir = typeof bData === 'object' && bData !== null && !Array.isArray(bData)
          if (aDir && !bDir) return -1
          if (!aDir && bDir) return 1
          return a.localeCompare(b)
        })
        children.push(
          h('div', { class: 'tree-children' },
            entries.map(([key, value]) =>
              h(TreeNode, {
                key,
                node: value,
                name: key,
                path: `${props.path}/${key}`,
                activePath: props.activePath,
                collapsedPaths: props.collapsedPaths,
                onToggle: (p) => emit('toggle', p),
                onSelect: (p) => emit('select', p)
              })
            )
          )
        )
      }

      const arrowClass = ['tree-arrow']
      if (!isDir.value) arrowClass.push('hidden')
      else if (!isCollapsed.value) arrowClass.push('open')

      const labelClass = ['tree-label']
      if (isActive.value) labelClass.push('active')

      return h('div', { class: 'tree-node' }, [
        h('div', {
          class: labelClass,
          onClick: () => {
            if (isDir.value) emit('toggle', props.path)
            else emit('select', props.path)
          }
        }, [
          h('span',
            { class: arrowClass, innerHTML: I.arrow, style: 'width:14px;height:14px;display:inline-flex' }
          ),
          h('span',
            {
              class: `type-${type.value}`,
              style: 'width:16px;height:16px;display:inline-flex;color:currentColor',
              innerHTML: iconForFileType(type.value)
            }
          ),
          h('span', { style: 'flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap' }, props.name)
        ]),
        ...children
      ])
    }
  }
})

watch(() => props.tree, () => {
  collapsedPaths.value = new Set()
  searchQuery.value = ''
})
</script>
