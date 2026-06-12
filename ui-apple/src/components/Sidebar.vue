<template>
  <aside class="sidebar glass">
    <!-- Header -->
    <div class="sidebar-header">
      <h3>Files</h3>
      <span class="badge">{{ fileCount }}</span>
    </div>

    <!-- Search -->
    <div class="search-box">
      <svg class="search-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <circle cx="11" cy="11" r="8" /><line x1="21" y1="21" x2="16.65" y2="16.65" />
      </svg>
      <input
        type="text"
        v-model="searchQuery"
        placeholder="Search files..."
        class="search-input"
      />
    </div>

    <!-- Tree -->
    <div class="tree-container" ref="treeContainerRef">
      <div v-if="!hasTree" class="empty-state">
        <p>Select a project to view files</p>
      </div>
      <div v-else-if="Object.keys(visibleTree).length === 0" class="empty-state">
        <p>No matching files</p>
      </div>
      <div v-else class="tree-list">
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
  </aside>
</template>

<script setup>
import { ref, computed, defineComponent, h } from 'vue'
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

const hasTree = computed(() => props.tree !== null)

function isNodeDir(node) {
  return typeof node === 'object' && node !== null && !Array.isArray(node)
}

function filterTree(node, query) {
  if (!query) return node
  const q = query.toLowerCase()
  const result = {}
  for (const [key, value] of Object.entries(node)) {
    if (key.toLowerCase().includes(q)) {
      result[key] = value
    } else if (isNodeDir(value)) {
      const filtered = filterTree(value, q)
      if (Object.keys(filtered).length > 0) {
        result[key] = filtered
      }
    }
  }
  return result
}

const visibleTree = computed(() => {
  if (!props.tree) return {}
  return filterTree(props.tree, searchQuery.value)
})

function togglePath(path) {
  const set = new Set(collapsedPaths.value)
  if (set.has(path)) {
    set.delete(path)
  } else {
    set.add(path)
  }
  collapsedPaths.value = set
}

// ── TreeNode (recursive render function) ──────────────────────
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
      const children = []
      if (isDir.value && !isCollapsed.value) {
        const entries = Object.entries(props.node)
        entries.sort(([a], [b]) => {
          const aIsDir = isNodeDir(props.node[a])
          const bIsDir = isNodeDir(props.node[b])
          if (aIsDir && !bIsDir) return -1
          if (!aIsDir && bIsDir) return 1
          return a.localeCompare(b)
        })
        for (const [key, child] of entries) {
          children.push(
            h(TreeNode, {
              node: child,
              name: key,
              path: props.path + '/' + key,
              activePath: props.activePath,
              collapsedPaths: props.collapsedPaths,
              onToggle: (p) => emit('toggle', p),
              onSelect: (p) => emit('select', p)
            })
          )
        }
      }

      return h('div', { class: 'tree-node' }, [
        h('div', {
          class: ['tree-item', { active: isActive.value }],
          onClick: handleClick
        }, [
          h('span', {
            class: 'tree-icon',
            innerHTML: isDir.value
              ? (isCollapsed.value ? chevronRight : chevronDown)
              : fileIcon(type.value)
          }),
          h('span', { class: 'tree-name' }, props.name)
        ]),
        children.length > 0 ? h('div', { class: 'tree-children' }, children) : null
      ])
    }
  }
})

// ── SVG Icons ─────────────────────────────────────────────────
const chevronDown = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 12 15 18 9"/></svg>'
const chevronRight = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="9 18 15 12 9 6"/></svg>'

function fileIcon(type) {
  const icons = {
    folder: '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg>',
    raw: '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>',
    wiki: '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"/><path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"/></svg>',
    graph: '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"/><path d="M12 1v4m0 14v4M4.22 4.22l2.83 2.83m9.9 9.9l2.83 2.83"/></svg>',
    concept: '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>',
    entity: '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>',
    source: '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/></svg>'
  }
  return icons[type] || icons.raw
}
</script>

<style scoped>
.sidebar {
  width: 260px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  border-radius: var(--radius-xl);
}

.sidebar-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 18px 12px;
}

.sidebar-header h3 {
  font-size: 0.8125rem;
  font-weight: 600;
  letter-spacing: 0.02em;
  color: var(--text-secondary);
  text-transform: uppercase;
}

.search-box {
  position: relative;
  padding: 0 12px 12px;
}

.search-icon {
  position: absolute;
  left: 22px;
  top: 50%;
  transform: translateY(-50%);
  width: 14px;
  height: 14px;
  color: var(--text-tertiary);
  pointer-events: none;
}

.search-input {
  padding-left: 34px;
  font-size: 0.8125rem;
  background: rgba(0, 0, 0, 0.03);
  border: 1px solid transparent;
  border-radius: var(--radius-sm);
}

.search-input:focus {
  background: rgba(0, 122, 255, 0.04);
  border-color: var(--accent);
}

.tree-container {
  flex: 1;
  overflow-y: auto;
  padding: 0 6px 8px;
}

.tree-list {
  padding: 0 4px;
}

/* ── Tree Node Styles ─────────────────────────────────────── */
.tree-node {
  user-select: none;
}

:deep(.tree-item) {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 5px 10px;
  border-radius: 8px;
  cursor: pointer;
  transition: background var(--transition-fast);
  font-size: 0.8125rem;
  color: var(--text-primary);
  letter-spacing: -0.01em;
}

:deep(.tree-item:hover) {
  background: rgba(0, 0, 0, 0.04);
}

:deep(.tree-item.active) {
  background: rgba(0, 122, 255, 0.08);
  color: var(--accent);
  font-weight: 500;
}

:deep(.tree-item.active .tree-icon) {
  color: var(--accent);
}

:deep(.tree-icon) {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 16px;
  height: 16px;
  flex-shrink: 0;
  color: var(--text-tertiary);
}

:deep(.tree-icon svg) {
  width: 14px;
  height: 14px;
  display: block;
}

:deep(.tree-name) {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex: 1;
}

:deep(.tree-children) {
  padding-left: 20px;
}
</style>