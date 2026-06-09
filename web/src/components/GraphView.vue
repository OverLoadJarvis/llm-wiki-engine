<template>
  <div class="graph-view">
    <div class="starfield" ref="starfieldRef"></div>
    <div ref="graphContainerRef" id="graph-container"></div>
    <div class="graph-legend" v-if="hasGraphData">
      <div class="legend-item"><div class="legend-dot" style="background:#86E8B8;color:#86E8B8"></div>source 源数据</div>
      <div class="legend-item"><div class="legend-dot" style="background:#3EB8FF;color:#3EB8FF"></div>entity 实体</div>
      <div class="legend-item"><div class="legend-dot" style="background:#FFD648;color:#FFD648"></div>concept 核心</div>
      <div class="legend-item"><div class="legend-dot" style="background:#E96FC2;color:#E96FC2"></div>synthesis 综合</div>
    </div>
    <div v-if="loading" class="loading">
      <div class="spinner"></div>
      <span>加载图谱中...</span>
    </div>
    <div v-if="!loading && !hasGraphData" class="empty-state">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
        <circle cx="12" cy="12" r="3"/><path d="M12 1v4m0 14v4M4.22 4.22l2.83 2.83m9.9 9.9l2.83 2.83M1 12h4m14 0h4"/>
      </svg>
      <p>暂无图谱数据</p>
      <button class="btn btn-sm" @click="$emit('build-graph')">构建图谱</button>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, watch, onBeforeUnmount, computed, nextTick } from 'vue'
import { Network, DataSet } from 'vis-network/standalone'

const props = defineProps({
  graphData: { type: Object, default: null },
  confidence: { type: Number, default: 0.3 },
  loading: { type: Boolean, default: false }
})

const emit = defineEmits(['node-click', 'update:confidence'])

const graphContainerRef = ref(null)
const starfieldRef = ref(null)
let network = null
let nudgeTimer = null

const nodeTypeConfig = {
  concept:   { bg: '#FFD648', border: '#D4B030', shape: 'dot',  borderWidth: 2.5 },
  entity:    { bg: '#3EB8FF', border: '#2A8FCC', shape: 'dot',  borderWidth: 2 },
  source:    { bg: '#86E8B8', border: '#5CB892', shape: 'dot',  borderWidth: 1.5 },
  synthesis: { bg: '#E96FC2', border: '#C04D9E', shape: 'box',  borderWidth: 2 },
  default:   { bg: '#6B7280', border: '#4B5563', shape: 'dot',  borderWidth: 1.5 }
}

const nodeTypeMap = ref({})
const adjacencyMap = ref(new Map())
const nodeIndex = ref(new Map())

const hasGraphData = computed(() => {
  return props.graphData && props.graphData.nodes && props.graphData.nodes.length > 0
})

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
    return { color: '#E96FC2', opacity: 0.2 }
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

  props.graphData.nodes.forEach(n => {
    const type = n.type || 'default'
    const cfg = nodeTypeConfig[type] || nodeTypeConfig.default
    typeMap[n.id] = type
    const opts = {
      id: n.id,
      label: n.label || n.id,
      color: {
        background: cfg.bg,
        border: cfg.border,
        highlight: { background: cfg.bg, border: '#fff' },
        hover: { background: cfg.bg, border: '#fff' }
      },
      font: { color: '#fff', size: 12, strokeWidth: 2, strokeColor: 'rgba(4,7,25,0.6)' },
      shape: cfg.shape,
      size: mapNodeSize(n.value),
      borderWidth: cfg.borderWidth,
      borderWidthSelected: 3.5,
      title: `${n.label || n.id}\n类型: ${type} · 连接数: ${n.value || 1}`,
      shadow: {
        enabled: true,
        color: cfg.bg + '80',
        size: 20,
        x: 0,
        y: 0
      }
    }
    if (type === 'synthesis') {
      opts.shapeProperties = { borderRadius: 8 }
    }
    nodes.add(opts)
  })

  nodeTypeMap.value = typeMap

  // adjacency map & node index
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

  // Apply edge filter by confidence
  applyEdgeFilter(edges, props.confidence)

  network = new Network(graphContainerRef.value, { nodes, edges }, {
    physics: {
      enabled: true,
      solver: 'forceAtlas2Based',
      minVelocity: 0.001,
      maxVelocity: 2,
      timestep: 0.4,
      forceAtlas2Based: {
        gravitationalConstant: -50,
        centralGravity: 0.002,
        springLength: 180,
        springConstant: 0.03,
        damping: 0.9
      },
      stabilization: { enabled: false }
    },
    interaction: { hover: true, tooltipDelay: 80, zoomView: true, dragView: true, dragNodes: true }
  })

  // Store references for interactive updates
  network._nodesDataSet = nodes
  network._edgesDataSet = edges
  network._nodeTypeMap = typeMap
  network._nodeTypeConfig = nodeTypeConfig
  network._nudgeActive = true
  network._hoverOrigSize = {}

  // Hover effect
  network.on('hoverNode', (params) => {
    const nodeId = params.node
    const ds = network._nodesDataSet
    const origNode = ds.get(nodeId)
    if (!origNode) return
    network._hoverOrigSize[nodeId] = origNode.size
    const type = typeMap[nodeId] || 'default'
    const cfg = nodeTypeConfig[type] || nodeTypeConfig.default
    ds.update({
      id: nodeId,
      size: origNode.size * 1.15,
      borderWidth: 4,
      shadow: { enabled: true, color: cfg.bg + 'CC', size: 30, x: 0, y: 0 }
    })
    if (graphContainerRef.value) {
      graphContainerRef.value.style.filter = `drop-shadow(0 0 20px ${cfg.bg}66) drop-shadow(0 0 60px ${cfg.bg}33)`
    }
  })

  network.on('blurNode', (params) => {
    const nodeId = params.node
    const ds = network._nodesDataSet
    const type = typeMap[nodeId] || 'default'
    const cfg = nodeTypeConfig[type] || nodeTypeConfig.default
    if (network._hoverOrigSize && network._hoverOrigSize[nodeId]) {
      ds.update({
        id: nodeId,
        size: network._hoverOrigSize[nodeId],
        borderWidth: cfg.borderWidth,
        shadow: { enabled: true, color: cfg.bg + '80', size: 20, x: 0, y: 0 }
      })
      delete network._hoverOrigSize[nodeId]
    }
    if (graphContainerRef.value) {
      graphContainerRef.value.style.filter = `drop-shadow(0 0 12px rgba(255, 214, 72, 0.08)) drop-shadow(0 0 40px rgba(62, 184, 255, 0.04))`
    }
  })

  network.on('zoom', () => {
    const scale = network.getScale()
    const factor = Math.min(1, Math.max(0.2, 1 / (scale * 0.8)))
    const ids = network.body.nodeIndices
    const ds = network._nodesDataSet
    for (let i = 0; i < ids.length; i += 3) {
      try {
        ds.update({ id: ids[i], opacity: Math.min(1, factor * 1.2) })
      } catch (_) {}
    }
  })

  // Nudge timer
  nudgeTimer = setInterval(() => {
    if (!network || !network._nudgeActive) return
    const ids = network.body.nodeIndices
    if (!ids || ids.length === 0) return
    const ds = network._nodesDataSet
    for (let i = 0; i < ids.length; i += 5) {
      try {
        const pos = network.getPosition(ids[i])
        network.moveNode(ids[i],
          pos.x + (Math.random() - 0.5) * 1.2,
          pos.y + (Math.random() - 0.5) * 1.2
        )
      } catch (_) {}
    }
  }, 2500)

  network.on('click', (params) => {
    if (network) {
      network._nudgeActive = false
      network.setOptions({ physics: { enabled: false } })
    }
    if (params.nodes.length > 0) {
      const nodeId = params.nodes[0]
      const node = props.graphData.nodes.find(n => n.id === nodeId)
      if (node) emit('node-click', node)
    }
  })
}

function applyEdgeFilter(edges, threshold) {
  if (!props.graphData || !props.graphData.edges) return
  const rawEdges = props.graphData.edges
  const ntm = nodeTypeMap.value
  const ecFn = edgeColor
  if (!edges) edges = network?._edgesDataSet
  if (!edges) return
  edges.clear()
  rawEdges.forEach(e => {
    const conf = e.confidence !== undefined ? e.confidence : 1
    if (conf < 0.3) return
    if (conf >= threshold) {
      const ft = ntm[e.from] || 'default'
      const tt = ntm[e.to] || 'default'
      const ec = ecFn(ft, tt)
      edges.add({
        from: e.from,
        to: e.to,
        label: '',
        color: { color: ec.color + Math.round(ec.opacity * 255).toString(16).padStart(2, '0'), highlight: ec.color + '66' },
        font: { color: 'rgba(255,255,255,0.3)', size: 9, align: 'top' },
        smooth: { type: 'continuous', roundness: 0.15 },
        width: 0.6 + conf * 0.6
      })
    }
  })
}

function createStarfield() {
  if (!starfieldRef.value) return
  const container = starfieldRef.value
  container.innerHTML = ''
  const w = container.offsetWidth || window.innerWidth
  const h = container.offsetHeight || window.innerHeight
  const count = Math.floor((w * h) / 8000)
  for (let i = 0; i < count; i++) {
    const star = document.createElement('div')
    star.className = 'star'
    const size = 0.5 + Math.random() * 1.5
    star.style.width = size + 'px'
    star.style.height = size + 'px'
    star.style.left = Math.random() * 100 + '%'
    star.style.top = Math.random() * 100 + '%'
    const alpha = 0.15 + Math.random() * 0.6
    star.style.opacity = alpha
    star.style.boxShadow = size > 1.2 ? `0 0 ${size * 2}px rgba(255,255,255,${alpha * 0.3})` : 'none'
    container.appendChild(star)
  }
}

watch(() => props.graphData, (newVal) => {
  if (newVal) {
    nextTick(() => renderGraph())
  }
}, { deep: true })

watch(() => props.confidence, (val) => {
  if (network) {
    applyEdgeFilter(network._edgesDataSet, val)
  }
})

onMounted(() => {
  createStarfield()
  if (props.graphData) {
    nextTick(() => renderGraph())
  }
  window.addEventListener('resize', createStarfield)
})

onBeforeUnmount(() => {
  destroyNetwork()
  window.removeEventListener('resize', createStarfield)
})

defineExpose({
  adjacencyMap,
  nodeIndex,
  nodeTypeMap
})
</script>
