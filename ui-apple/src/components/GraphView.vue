<template>
  <div class="graph-view">
    <!-- Starfield Background -->
    <canvas ref="starfieldRef" class="starfield"></canvas>

    <!-- Graph Container -->
    <div ref="graphContainerRef" class="graph-container"></div>

    <!-- Legend -->
    <div class="graph-legend glass-subtle" v-if="hasGraphData">
      <div class="legend-item">
        <span class="legend-dot" style="background:#34C759"></span> Source
      </div>
      <div class="legend-item">
        <span class="legend-dot" style="background:#007AFF"></span> Entity
      </div>
      <div class="legend-item">
        <span class="legend-dot" style="background:#FF9500"></span> Concept
      </div>
      <div class="legend-item">
        <span class="legend-dot" style="background:#AF52DE"></span> Synthesis
      </div>
    </div>

    <!-- Loading -->
    <div v-if="loading" class="loading-overlay">
      <div class="loading-card glass">
        <div class="spinner"></div>
        <span>Loading graph...</span>
      </div>
    </div>

    <!-- Empty State -->
    <div v-if="!loading && !hasGraphData" class="empty-overlay">
      <div class="empty-card glass">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
          <circle cx="12" cy="12" r="3" />
          <path d="M12 1v4m0 14v4M4.22 4.22l2.83 2.83m9.9 9.9l2.83 2.83M1 12h4m14 0h4" />
        </svg>
        <p>No graph data available</p>
        <button class="btn btn-sm" @click="$emit('build-graph')">Build Graph</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, watch, onBeforeUnmount, computed } from 'vue'
import { Network, DataSet } from 'vis-network/standalone'

const props = defineProps({
  graphData: { type: Object, default: null },
  confidence: { type: Number, default: 0.3 },
  loading: { type: Boolean, default: false }
})

const emit = defineEmits(['node-click', 'build-graph', 'update:confidence'])

const graphContainerRef = ref(null)
const starfieldRef = ref(null)
let network = null
let nudgeTimer = null
let starfieldAnimId = null

const nodeTypeConfig = {
  concept:   { bg: '#FF9500', border: '#CC7A00', shape: 'dot', borderWidth: 2.5 },
  entity:    { bg: '#007AFF', border: '#005FCC', shape: 'dot', borderWidth: 2 },
  source:    { bg: '#34C759', border: '#28A745', shape: 'dot', borderWidth: 1.5 },
  synthesis: { bg: '#AF52DE', border: '#8E3DB5', shape: 'box', borderWidth: 2 },
  default:   { bg: '#8E8E93', border: '#6E6E73', shape: 'dot', borderWidth: 1.5 }
}

const nodeTypeMap = ref({})
const adjacencyMap = ref(new Map())
const nodeIndex = ref(new Map())

const hasGraphData = computed(() => {
  return props.graphData && props.graphData.nodes && props.graphData.nodes.length > 0
})

// ── Starfield Animation ───────────────────────────────────────
function initStarfield() {
  const canvas = starfieldRef.value
  if (!canvas) return
  const ctx = canvas.getContext('2d')
  const stars = []
  const STAR_COUNT = 80

  function resize() {
    const rect = canvas.parentElement.getBoundingClientRect()
    canvas.width = rect.width * window.devicePixelRatio
    canvas.height = rect.height * window.devicePixelRatio
    canvas.style.width = rect.width + 'px'
    canvas.style.height = rect.height + 'px'
    ctx.scale(window.devicePixelRatio, window.devicePixelRatio)
  }

  resize()
  window.addEventListener('resize', resize)

  for (let i = 0; i < STAR_COUNT; i++) {
    stars.push({
      x: Math.random() * canvas.width / window.devicePixelRatio,
      y: Math.random() * canvas.height / window.devicePixelRatio,
      r: Math.random() * 1.2 + 0.3,
      opacity: Math.random() * 0.5 + 0.1,
      speed: Math.random() * 0.003 + 0.001,
      phase: Math.random() * Math.PI * 2
    })
  }

  function animate() {
    const w = canvas.width / window.devicePixelRatio
    const h = canvas.height / window.devicePixelRatio
    ctx.clearRect(0, 0, w, h)

    const time = Date.now() * 0.001
    for (const star of stars) {
      star.opacity += Math.sin(time * star.speed * 10 + star.phase) * 0.002
      star.opacity = Math.max(0.05, Math.min(0.6, star.opacity))
      ctx.beginPath()
      ctx.arc(star.x, star.y, star.r, 0, Math.PI * 2)
      ctx.fillStyle = `rgba(0, 122, 255, ${star.opacity})`
      ctx.fill()
    }

    starfieldAnimId = requestAnimationFrame(animate)
  }

  animate()

  onBeforeUnmount(() => {
    cancelAnimationFrame(starfieldAnimId)
    window.removeEventListener('resize', resize)
  })
}

// ── Graph Rendering ───────────────────────────────────────────
function mapNodeSize(value) {
  const v = Math.max(value || 1, 1)
  return Math.min(40, 12 + Math.log2(v) * 6)
}

function edgeColor(fromType, toType) {
  if ((fromType === 'concept' && toType === 'entity') || (fromType === 'entity' && toType === 'concept'))
    return { color: '#63C7FF', opacity: 0.35 }
  if ((fromType === 'entity' && toType === 'source') || (fromType === 'source' && toType === 'entity'))
    return { color: '#B6E3F7', opacity: 0.2 }
  if ((fromType === 'concept' && toType === 'source') || (fromType === 'source' && toType === 'concept'))
    return { color: '#A8D5BA', opacity: 0.2 }
  if ((fromType === 'synthesis' && toType === 'concept') || (fromType === 'concept' && toType === 'synthesis'))
    return { color: '#D98BC8', opacity: 0.3 }
  if (fromType === 'synthesis' || toType === 'synthesis')
    return { color: '#AF52DE', opacity: 0.2 }
  return { color: '#63C7FF', opacity: 0.2 }
}

function destroyNetwork() {
  if (nudgeTimer) {
    clearInterval(nudgeTimer)
    nudgeTimer = null
  }
  if (network) {
    network.destroy()
    network = null
  }
}

function renderGraph() {
  if (!graphContainerRef.value) return
  if (!props.graphData || !props.graphData.nodes) return

  destroyNetwork()

  const nodes = new DataSet()
  const edges = new DataSet()
  const typeMap = {}
  const adjMap = new Map()
  const nIdx = new Map()

  props.graphData.nodes.forEach(n => {
    const type = n.type || 'default'
    const cfg = nodeTypeConfig[type] || nodeTypeConfig.default
    const size = mapNodeSize(n.value || n.size || 1)
    typeMap[n.id] = type
    nIdx.set(n.id, n)

    nodes.add({
      id: n.id,
      label: (n.label || String(n.id)).substring(0, 28),
      color: { background: cfg.bg, border: cfg.border, highlight: { background: cfg.bg, border: '#fff' } },
      borderWidth: cfg.borderWidth,
      shape: cfg.shape,
      size: size,
      font: { color: '#1D1D1F', size: 11, face: 'Inter', strokeWidth: 0 }
    })
  })

  if (props.graphData.edges) {
    props.graphData.edges.forEach(e => {
      if (!adjMap.has(e.from)) adjMap.set(e.from, new Set())
      if (!adjMap.has(e.to)) adjMap.set(e.to, new Set())
      adjMap.get(e.from).add(e.to)
      adjMap.get(e.to).add(e.from)

      const ec = edgeColor(typeMap[e.from] || 'default', typeMap[e.to] || 'default')
      const weight = e.weight || e.confidence || 1
      if (weight < props.confidence) return

      edges.add({
        from: e.from,
        to: e.to,
        color: { color: ec.color, opacity: ec.opacity },
        width: Math.min(3, Math.max(0.5, weight * 1.5)),
        smooth: { type: 'continuous', roundness: 0.5 }
      })
    })
  }

  nodeTypeMap.value = typeMap
  adjacencyMap.value = adjMap
  nodeIndex.value = nIdx

  const options = {
    physics: {
      solver: 'forceAtlas2Based',
      forceAtlas2Based: {
        gravitationalConstant: -40,
        centralGravity: 0.01,
        springLength: 150,
        springConstant: 0.05,
        damping: 0.3
      },
      stabilization: { iterations: 200 }
    },
    interaction: {
      hover: true,
      zoomView: true,
      dragView: true,
      navigationButtons: false
    },
    edges: {
      smooth: { type: 'continuous', roundness: 0.5 }
    }
  }

  network = new Network(graphContainerRef.value, { nodes, edges }, options)

  network.on('click', function (params) {
    if (params.nodes.length > 0) {
      const nodeId = params.nodes[0]
      const nodeData = nIdx.get(nodeId)
      if (nodeData) {
        emit('node-click', nodeData)
      }
    }
  })

  // Gentle nudge to keep graph alive
  nudgeTimer = setInterval(() => {
    if (network) {
      network.moveNode({ id: nodes.get()[0]?.id, x: 0, y: 0 })
      network.moveNode({ id: nodes.get()[0]?.id, x: undefined, y: undefined })
    }
  }, 30000)
}

// ── Lifecycle ─────────────────────────────────────────────────
onMounted(() => {
  initStarfield()
  if (props.graphData) {
    renderGraph()
  }
})

watch(() => props.graphData, () => {
  if (props.graphData) {
    renderGraph()
  }
})

watch(() => props.confidence, () => {
  if (props.graphData) {
    renderGraph()
  }
})

onBeforeUnmount(() => {
  destroyNetwork()
})
</script>

<style scoped>
.graph-view {
  width: 100%;
  height: 100%;
  position: relative;
  overflow: hidden;
  border-radius: var(--radius-xl);
  background: #FAFAFA;
}

.starfield {
  position: absolute;
  inset: 0;
  z-index: 0;
  pointer-events: none;
}

.graph-container {
  position: absolute;
  inset: 0;
  z-index: 1;
}

.graph-legend {
  position: absolute;
  bottom: 16px;
  left: 16px;
  z-index: 10;
  display: flex;
  gap: 14px;
  padding: 8px 16px;
  border-radius: var(--radius-sm);
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 0.6875rem;
  font-weight: 500;
  color: var(--text-secondary);
  letter-spacing: 0.02em;
}

.legend-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  box-shadow: 0 0 6px currentColor;
}

.loading-overlay,
.empty-overlay {
  position: absolute;
  inset: 0;
  z-index: 20;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(245, 245, 247, 0.6);
  backdrop-filter: blur(4px);
}

.loading-card,
.empty-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 14px;
  padding: 32px 48px;
  border-radius: var(--radius-xl);
  animation: fadeInUp 400ms var(--ease-out-expo);
}

.empty-card svg {
  width: 48px;
  height: 48px;
  color: var(--text-tertiary);
  opacity: 0.4;
}

.empty-card p {
  font-size: 0.875rem;
  color: var(--text-secondary);
}
</style>