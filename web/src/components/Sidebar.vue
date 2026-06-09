<template>
  <div class="sidebar">
    <div class="sidebar-header">
      <h3>文件浏览器</h3>
      <span class="badge">{{ fileCount }} 文件</span>
    </div>
    <div class="search-box">
      <input type="text" v-model="searchQuery" placeholder="搜索文件..." />
    </div>
    <div class="tree-container" ref="treeContainerRef">
      <div v-if="!hasTree" class="empty-state" style="padding: 40px 16px;">
        <p>选择项目以查看文件</p>
      </div>
      <div v-else-if="Object.keys(visibleTree).length === 0" class="empty-state" style="padding: 40px 16px;">
        <p>没有匹配的文件</p>
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
          @select="$emit('select-file', $event)"
        />
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, defineComponent, h } from 'vue'
import { getFileType } from '../utils/api.js'

const props = defineProps({
  tree: { type: Object, default: null },
  fileCount: { type: Number, default: 0 },
  activePath: { type: String, default: '' }
})

defineEmits(['select-file'])

const searchQuery = ref('')
const collapsedPaths = ref(new Set())
const treeContainerRef = ref(null)

function iconSvg(type) {
  const icons = {
    folder: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg>',
    raw: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>',
    wiki: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"/><path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"/></svg>',
    graph: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="3"/><path d="M12 1v4m0 14v4M4.22 4.22l2.83 2.83m9.9 9.9l2.83 2.83"/></svg>',
    concept: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>',
    entity: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>',
    source: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/></svg>'
  }
  return icons[type] || icons.raw
}

function isNodeDir(node) {
  return typeof node === 'object' && node !== null && !Array.isArray(node)
}

// ── TreeNode (recursive, render function) ─────────────────────────
const TreeNode = defineComponent({
  name: 'TreeNode',
  props: {
    node: { type: [Object, Array, Number], required: true },
    name: { type: String, required: true },
    path: { type: String, required: true },
    activePath: { type: String, default: '' },
    collapsedPaths: { type: Set, default: () => new Set() }
  },
  emits: ['toggle', 'select'],
  setup(props, { emit }) {
    // ⚠️ 必须使用 computed()，否则在 setup() 中读取一次后不会随父级状态变化
    const isDir = computed(() => isNodeDir(props.node))
    const isCollapsed = computed(() => props.collapsedPaths.has(props.path))
    const type = computed(() => (isDir.value ? 'folder' : getFileType(props.path)))
    const isActive = computed(() => props.activePath === props.path)

    function handleClick() {
      if (isDir.value) {
        emit('toggle', props.path)
      } else {
        emit('select', props.path)
      }
    }

    return () => {
      let children = null
      if (isDir.value && !isCollapsed.value) {
        const entries = Object.entries(props.node)
        entries.sort(([a], [b]) => {
          const aIsDir = isNodeDir(props.node[a])
          const bIsDir = isNodeDir(props.node[b])
          if (aIsDir && !bIsDir) return -1
          if (!aIsDir && bIsDir) return 1
          return a.localeCompare(b)
        })
        children = h('div',
          { class: 'tree-children' },
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
      }

      const arrowClass = ['arrow']
      if (isDir.value) {
        if (!isCollapsed.value) arrowClass.push('open')
      } else {
        arrowClass.push('hidden')
      }

      const labelClass = ['tree-label']
      if (isActive.value) labelClass.push('active')

      return h('div', { class: 'tree-node' }, [
        h('div',
          { class: labelClass, onClick: handleClick },
          [
            h('span', {
              class: arrowClass,
              innerHTML: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="9 18 15 12 9 6"/></svg>'
            }),
            h('span', {
              class: ['icon', `type-${type.value}`],
              innerHTML: iconSvg(type.value)
            }),
            h('span', props.name)
          ]
        ),
        children
      ])
    }
  }
})

// ── 顶层逻辑 ──────────────────────────────────────────────────────

const hasTree = computed(() => !!props.tree && Object.keys(props.tree).length > 0)

function filterTree(node, query, path) {
  if (isNodeDir(node)) {
    const result = {}
    let anyMatch = false
    for (const [key, child] of Object.entries(node)) {
      const childPath = path ? `${path}/${key}` : key
      const filtered = filterTree(child, query, childPath)
      if (filtered !== null) {
        result[key] = filtered
        anyMatch = true
      }
    }
    return anyMatch ? result : null
  }
  return path.toLowerCase().includes(query) ? node : null
}

const visibleTree = computed(() => {
  if (!props.tree) return {}
  const query = searchQuery.value.trim().toLowerCase()
  if (!query) return props.tree
  const filtered = filterTree(props.tree, query, '')
  return filtered || {}
})

function togglePath(path) {
  // 替换整个 Set 以触发响应式更新（Vue 3 的 ref 对 Set 内部变更不追踪）
  const next = new Set(collapsedPaths.value)
  if (next.has(path)) {
    next.delete(path)
  } else {
    next.add(path)
  }
  collapsedPaths.value = next
}

watch(() => props.tree, (newTree) => {
  if (newTree) {
    collapsedPaths.value = new Set()
    searchQuery.value = ''
  }
})
</script>
