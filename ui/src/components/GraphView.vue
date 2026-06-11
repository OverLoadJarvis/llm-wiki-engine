<template>
  <div class="graph-view" style="position:relative;flex:1">
    <div v-if="!loading && hasGraphData" class="scan-sweep"></div>
    <div id="graph-canvas" ref="graphContainerRef"></div>

    <div v-if="hasGraphData && !loading" class="hud-overlay">
      <div class="graph-stats">
        <div class="stat-card reveal">
          <div class="stat-label">NODES</div>
          <div class="stat-value">{{ nodeCount }}</div>
        </div>
        <div class="stat-card reveal-delay-1">
          <div class="stat-label">EDGES</div>
          <div class="stat-value">{{ edgeCount }}</div>
        </div>
        <div class="stat-card reveal-delay-2">
          <div class="stat-label">CONF.</div>
          <div class="stat-value">{{ Math.round(confidence * 100) }}%</div>
        </div>
      </div>

      <div class="graph-legend">
        <div class="legend-item"><span class="legend-dot" style="background:#00F0FF;box-shadow:0 0 8px #00F0FF"></span>source</div>
        <div class="legend-item"><span class="legend-dot" style="background:#FF2D95;box-shadow:0 0 8px #FF2D95"></span>entity</div>
        <div class="legend-item"><span class="legend-dot" style="background:#8A4BFF;box-shadow:0 0 8px #8A4BFF"></span>concept</div>
        <div class="legend-item"><span class="legend-dot" style="background:#00FF88;box-shadow:0 0 8px #00FF88"></span>synthesis</div>
      </div>
    </div>

    <div v-if="loading" class="empty-state" style="position:absolute;inset:0">
      <div class="loading-wrap">
        <div class="spinner-ring"></div>
        <div>Rendering knowledge graph...</div>
      </div>
    </div>

    <div v-if="!loading && !hasGraphData" class="empty-state" style="position:absolute;inset:0">
      <span v-html="I.network" style="width:96px;height:96px;color:var(--neon-cyan);opacity:0.5"></span>
      <h2>No graph data</h2>
      <p>Build a knowledge graph first to visualize connections between your concepts, entities, and sources.</p>
      <button class="btn btn-primary" @click="$emit('build-graph')">
        <span v-html="I.play" style="width:14px;height:14px"></span>
        Build Graph
      </button>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, watch, onBeforeUnmount, computed, nextTick } from 'vue'
import { Network, DataSet } from 'vis-network/standalone/esm/vis-network.js'
import { I } from '../utils/icons.js'

const props = defineProps({
  graphData: { type: Object, default: null },
  confidence: { type: Number, default: 0.3 },
  loading: { type: Boolean, default: false }
})

const emit = defineEmits(['node-click'])

const graphContainerRef = ref(null)
let network = null

const nodeTypeConfig = {
  concept:   { bg: '#8A4BFF', border: '#B48AFF', shape: 'dot' },
  entity:    { bg: '#FF2D95', border: '#FF8CC0', shape: 'dot' },
  source:    { bg: '#00F0FF', border: '#80F7FF', shape: 'dot' },
  synthesis: { bg: '#00FF88', border: '#7DFFC0', shape: 'box' },
  default:   { bg: '#6B7280', border: '#9CA3AF', shape: 'dot' }
}

const nodeTypeMap = ref({})
const adjacencyMap = ref(new Map())
const nodeIndex = ref(new Map())

const hasGraphData = computed(() => {
  return props.graphData && props.graphData.nodes && props.graphData.nodes.length > 0
})
const nodeCount = computed(() => props.graphData?.nodes?.length || 0)
const edgeCount = computed(() => {
  if (!props.graphData?.edges) return 0
  return props.graphData.edges.filter(e => (e.confidence ?? 1) >= props.confidence).length
})

function mapNodeSize(value) {
  const v = Math.max(value || 1, 1)
  return Math.min(36, 12 + Math.log2(v) * 5)
}

function renderGraph() {
  if (!graphContainerRef.value) return
  if (!props.graphData || !props.graphData.nodes) return

  destroyNetwork()

  const nodes = new DataSet()
  const typeMap = {}

  props.graphData.nodes.forEach(n => {
    const type = n.type || 'default'
    const cfg = nodeTypeConfig[type] || nodeTypeConfig.default
    typeMap[n.id] = type
    nodes.add({
      id: n.id,
      label: n.label || n.id,
      color: {
        background: cfg.bg,
        border: cfg.border,
        highlight: { background: cfg.bg, border: '#FFFFFF' },
        hover: { background: cfg.bg, border: '#FFFFFF' }
      },
      font: { color: '#E8F1FF', size: 12, face: 'Orbitron, sans-serif', strokeWidth: 2, strokeColor: 'rgba(5,7,15,0.85)' },
      shape: cfg.shape,
      size: mapNodeSize(n.value),
      borderWidth: 1.5,
      borderWidthSelected: 3,
      title: `${n.label || n.id}\ntype: ${type} · connections: ${n.value || 1}`,
      shadow: { enabled: true, color: cfg.bg + '80', size: 15, x: 0, y: 0 }
    })
  })

  nodeTypeMap.value = typeMap

  // Build adjacency map & node index for detail panel
  const adj = new Map()
  const nIdx = new Map()
  props.graphData.nodes.forEach(n => nIdx.set(n.id, n))
  if (props.graphData.edges) {
    props.graphData.edges.forEach(e => {
      if (!adj.has(e.from)) adj.set(e.from, new Set())
      if (!adj.has(e.to)) adj.set(e.to, new Set())
      adj.get(e.from).add(e.to)
      adj.get(e.to).add(e.from)
    })
  }
  adjacencyMap.value = adj
  nodeIndex.value = nIdx

  const edges = buildEdges(typeMap)
  const edgesDS = new DataSet(edges)

  network = new Network(graphContainerRef.value, { nodes: nodes, edges: edgesDS }, {
    physics: {
      enabled: true,
      solver: 'forceAtlas2Based',
      minVelocity: 0.001,
      maxVelocity: 3,
      timestep: 0.35,
      forceAtlas2Based: {
        gravitationalConstant: -60,
        centralGravity: 0.005,
        springLength: 160,
        springConstant: 0.04,
        damping: 0.92
      },
      stabilization: { enabled: true, iterations: 80, updateInterval: 20 }
    },
    interaction: { hover: true, tooltipDelay: 120, zoomView: true, dragView: true, dragNodes: true, hideEdgesOnDrag: false },
    nodes: { shadow: { enabled: true } },
    edges: { color: { inherit: false }, smooth: { type: 'continuous', roundness: 0.2 }, hoverWidth: 1.2 },
    layout: { improvedLayout: false }
  })

  // Ensure nodes are fitted to visible area after physics stabilization
  network.once('stabilizationIterationsDone', () => {
    if (network) network.fit({ animation: { duration: 400, easingFunction: 'easeInOutQuad' } })
  })

  network.on('click', (params) => {
    if (params.nodes.length > 0) {
      const nodeId = params.nodes[0]
      const node = props.graphData.nodes.find(n => n.id === nodeId)
      if (node) emit('node-click', node)
    }
  })

  // Hover effect: subtly highlight
  network.on('hoverNode', () => {
    if (graphContainerRef.value) {
      graphContainerRef.value.style.filter = 'drop-shadow(0 0 18px rgba(0,240,255,0.25))'
    }
  })
  network.on('blurNode', () => {
    if (graphContainerRef.value) graphContainerRef.value.style.filter = ''
  })
}

function buildEdges(typeMap) {
  if (!props.graphData?.edges) return []
  const threshold = props.confidence
  return props.graphData.edges
    .filter(e => (e.confidence ?? 1) >= threshold)
    .map(e => {
      const color = edgeColor(typeMap[e.from], typeMap[e.to])
      return {
        from: e.from,
        to: e.to,
        color: { color: color, opacity: 0.5, highlight: color },
        width: 0.8 + (e.confidence ?? 0.5) * 0.8
      }
    })
}

function edgeColor(fromType, toType) {
  const pair = [fromType, toType].sort().join('-')
  const palette = {
    'concept-entity': '#B48AFF',
    'concept-source': '#4DD0FF',
    'entity-source': '#FF8CC0',
    'concept-synthesis': '#00FF88',
    'concept-concept': '#8A4BFF',
    'entity-entity': '#FF2D95',
    'source-source': '#00F0FF'
  }
  return palette[pair] || '#00F0FF'
}

function destroyNetwork() {
  if (network) {
    network.destroy()
    network = null
  }
}

// Re-render when graph data changes
watch(() => props.graphData, (newVal) => {
  if (newVal) nextTick(() => renderGraph())
}, { deep: true })

// Update edges when confidence changes
watch(() => props.confidence, () => {
  if (network && props.graphData?.edges) {
    const edges = buildEdges(nodeTypeMap.value)
    const body = network.body
    if (body && body.data && body.data.edges) {
      body.data.edges.clear()
      body.data.edges.add(edges)
    }
  }
})

let resizeHandler = null
onMounted(() => {
  if (props.graphData && hasGraphData.value) nextTick(() => renderGraph())
  resizeHandler = () => {
    if (network) network.redraw()
  }
  window.addEventListener('resize', resizeHandler)
})

onBeforeUnmount(() => {
  destroyNetwork()
  if (resizeHandler) window.removeEventListener('resize', resizeHandler)
})

defineExpose({
  adjacencyMap,
  nodeIndex
})
</script>
