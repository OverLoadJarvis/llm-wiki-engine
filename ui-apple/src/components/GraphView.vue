<template>
  <div class="graph-view">
    <!-- Enhanced Starfield + Particle Backdrop -->
    <canvas ref="starfieldRef" class="starfield"></canvas>

    <!-- Ambient Glow Layer -->
    <div class="ambient-glow"></div>

    <!-- Graph Container -->
    <div ref="graphContainerRef" class="graph-container"></div>

    <!-- Floating Particle Overlay -->
    <canvas ref="particlesRef" class="particles-overlay"></canvas>

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

    <!-- Stats Badge -->
    <div class="stats-badge glass-subtle" v-if="hasGraphData">
      <div class="stat-item">
        <span class="stat-num">{{ nodeCount }}</span>
        <span class="stat-label">Nodes</span>
      </div>
      <div class="stat-divider"></div>
      <div class="stat-item">
        <span class="stat-num">{{ edgeCount }}</span>
        <span class="stat-label">Links</span>
      </div>
    </div>

    <!-- Loading -->
    <div v-if="loading" class="loading-overlay">
      <div class="loading-card glass">
        <div class="spinner">
          <div class="spinner-ring"></div>
          <div class="spinner-core"></div>
        </div>
        <span>Weaving knowledge graph...</span>
      </div>
    </div>

    <!-- Empty State -->
    <div v-if="!loading && !hasGraphData" class="empty-overlay">
      <div class="empty-card glass">
        <div class="empty-icon-ring">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
            <circle cx="12" cy="12" r="3" />
            <circle cx="4" cy="5" r="1.5" />
            <circle cx="20" cy="5" r="1.5" />
            <circle cx="4" cy="19" r="1.5" />
            <circle cx="20" cy="19" r="1.5" />
            <path d="M5.5 5.5 L10.5 11 M18.5 5.5 L13.5 11 M5.5 18.5 L10.5 13 M18.5 18.5 L13.5 13" />
          </svg>
        </div>
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
const particlesRef = ref(null)
let network = null
let starfieldAnimId = null
let particlesAnimId = null
let hoverNodeId = null
let pulsePhase = 0

const nodeTypeConfig = {
  concept:   { bg: '#FF9500', border: '#FFB340', shape: 'dot', borderWidth: 2, glow: 'rgba(255, 149, 0, 0.4)' },
  entity:    { bg: '#007AFF', border: '#5AC8FA', shape: 'dot', borderWidth: 2, glow: 'rgba(0, 122, 255, 0.4)' },
  source:    { bg: '#34C759', border: '#7EE081', shape: 'dot', borderWidth: 1.5, glow: 'rgba(52, 199, 89, 0.3)' },
  synthesis: { bg: '#AF52DE', border: '#D98BC8', shape: 'dot', borderWidth: 2.5, glow: 'rgba(175, 82, 222, 0.5)' },
  default:   { bg: '#8E8E93', border: '#C7C7CC', shape: 'dot', borderWidth: 1.5, glow: 'rgba(142, 142, 147, 0.3)' }
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
  return props.graphData.edges.filter(e => (e.weight || e.confidence || 1) >= props.confidence).length
})

// ── Starfield + Meteor Animation ─────────────────────────────
function initStarfield() {
  const canvas = starfieldRef.value
  if (!canvas) return
  const ctx = canvas.getContext('2d')
  const stars = []
  const meteors = []
  const STAR_COUNT = 120
  const METEOR_COUNT = 3

  function resize() {
    const rect = canvas.parentElement.getBoundingClientRect()
    canvas.width = rect.width * window.devicePixelRatio
    canvas.height = rect.height * window.devicePixelRatio
    canvas.style.width = rect.width + 'px'
    canvas.style.height = rect.height + 'px'
    ctx.setTransform(1, 0, 0, 1, 0, 0)
    ctx.scale(window.devicePixelRatio, window.devicePixelRatio)
  }

  resize()
  window.addEventListener('resize', resize)

  // Init stars with parallax layers
  for (let i = 0; i < STAR_COUNT; i++) {
    const layer = Math.floor(Math.random() * 3)
    stars.push({
      x: Math.random() * canvas.width / window.devicePixelRatio,
      y: Math.random() * canvas.height / window.devicePixelRatio,
      r: layer === 0 ? Math.random() * 0.6 + 0.2 : layer === 1 ? Math.random() * 1.0 + 0.4 : Math.random() * 1.6 + 0.6,
      baseOpacity: layer === 0 ? 0.15 : layer === 1 ? 0.3 : 0.5,
      opacity: Math.random() * 0.5 + 0.1,
      twinkleSpeed: Math.random() * 0.8 + 0.3,
      twinklePhase: Math.random() * Math.PI * 2,
      color: Math.random() > 0.85 ? '#5AC8FA' : (Math.random() > 0.6 ? '#AF52DE' : '#007AFF')
    })
  }

  // Init meteors
  function spawnMeteor() {
    const w = canvas.width / window.devicePixelRatio
    const h = canvas.height / window.devicePixelRatio
    meteors.push({
      x: Math.random() * w * 0.6 - w * 0.1,
      y: Math.random() * h * 0.4,
      vx: Math.random() * 6 + 4,
      vy: Math.random() * 3 + 2,
      length: Math.random() * 80 + 60,
      life: 1,
      decay: 0.005 + Math.random() * 0.005
    })
  }

  function animate() {
    const w = canvas.width / window.devicePixelRatio
    const h = canvas.height / window.devicePixelRatio

    // Fade trail effect
    ctx.fillStyle = 'rgba(250, 250, 250, 0.15)'
    ctx.fillRect(0, 0, w, h)

    const time = Date.now() * 0.001

    // Draw stars with twinkle
    for (const star of stars) {
      const twinkle = Math.sin(time * star.twinkleSpeed + star.twinklePhase)
      star.opacity = star.baseOpacity + twinkle * 0.3
      star.opacity = Math.max(0.05, Math.min(1, star.opacity))

      ctx.beginPath()
      ctx.arc(star.x, star.y, star.r, 0, Math.PI * 2)
      ctx.fillStyle = star.color.replace(')', `, ${star.opacity})`).replace('rgb', 'rgba')
      // Simple fallback
      ctx.fillStyle = `rgba(${hexToRgb(star.color)}, ${star.opacity})`
      ctx.fill()
    }

    // Draw meteors
    if (Math.random() < 0.008 && meteors.length < METEOR_COUNT) {
      spawnMeteor()
    }

    for (let i = meteors.length - 1; i >= 0; i--) {
      const m = meteors[i]
      m.x += m.vx
      m.y += m.vy
      m.life -= m.decay

      if (m.life <= 0 || m.x > w + 100 || m.y > h + 100) {
        meteors.splice(i, 1)
        continue
      }

      // Meteor tail gradient
      const gradient = ctx.createLinearGradient(m.x, m.y, m.x - m.vx * m.length / 3, m.y - m.vy * m.length / 3)
      gradient.addColorStop(0, `rgba(90, 200, 250, ${m.life})`)
      gradient.addColorStop(0.3, `rgba(0, 122, 255, ${m.life * 0.5})`)
      gradient.addColorStop(1, 'rgba(0, 122, 255, 0)')

      ctx.beginPath()
      ctx.moveTo(m.x, m.y)
      ctx.lineTo(m.x - m.vx * m.length / 3, m.y - m.vy * m.length / 3)
      ctx.strokeStyle = gradient
      ctx.lineWidth = 2 * m.life
      ctx.lineCap = 'round'
      ctx.stroke()

      // Meteor head
      ctx.beginPath()
      ctx.arc(m.x, m.y, 2 * m.life, 0, Math.PI * 2)
      ctx.fillStyle = `rgba(255, 255, 255, ${m.life})`
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

function hexToRgb(hex) {
  const r = parseInt(hex.slice(1, 3), 16)
  const g = parseInt(hex.slice(3, 5), 16)
  const b = parseInt(hex.slice(5, 7), 16)
  return `${r}, ${g}, ${b}`
}

// ── Particle Overlay (Orbit rings + glow pulses around nodes) ─
function initParticles() {
  const canvas = particlesRef.value
  if (!canvas) return
  const ctx = canvas.getContext('2d')
  const orbits = []
  const freeParticles = []

  function resize() {
    const rect = canvas.parentElement.getBoundingClientRect()
    canvas.width = rect.width * window.devicePixelRatio
    canvas.height = rect.height * window.devicePixelRatio
    canvas.style.width = rect.width + 'px'
    canvas.style.height = rect.height + 'px'
    ctx.setTransform(1, 0, 0, 1, 0, 0)
    ctx.scale(window.devicePixelRatio, window.devicePixelRatio)
  }
  resize()
  window.addEventListener('resize', resize)

  // Initial free-floating particles
  for (let i = 0; i < 15; i++) {
    freeParticles.push({
      x: Math.random() * canvas.width / window.devicePixelRatio,
      y: Math.random() * canvas.height / window.devicePixelRatio,
      vx: (Math.random() - 0.5) * 0.3,
      vy: (Math.random() - 0.5) * 0.3,
      r: Math.random() * 2 + 1,
      color: Math.random() > 0.5 ? '#5AC8FA' : '#AF52DE',
      opacity: Math.random() * 0.3 + 0.1
    })
  }

  function animate() {
    const w = canvas.width / window.devicePixelRatio
    const h = canvas.height / window.devicePixelRatio
    ctx.clearRect(0, 0, w, h)

    pulsePhase += 0.02
    const time = Date.now() * 0.001

    // Get node positions from vis-network
    let nodePositions = []
    if (network && nodeIndex.value.size > 0) {
      try {
        const positions = network.getPositions()
        const viewPos = network.getViewPosition()
        const scale = network.getScale()
        const canvasRect = graphContainerRef.value?.getBoundingClientRect()
        const cx = canvasRect ? canvasRect.width / 2 : w / 2
        const cy = canvasRect ? canvasRect.height / 2 : h / 2

        for (const [id, pos] of Object.entries(positions)) {
          const screenX = cx + (pos.x - viewPos.x) * scale
          const screenY = cy + (pos.y - viewPos.y) * scale
          const type = nodeTypeMap.value[id] || 'default'
          const cfg = nodeTypeConfig[type]
          const isHovered = id === hoverNodeId
          const nodeData = nodeIndex.value.get(id)
          const baseSize = mapNodeSize(nodeData?.value || nodeData?.size || 1)
          nodePositions.push({
            x: screenX, y: screenY, color: cfg.bg, glow: cfg.glow, type, isHovered, size: baseSize, id
          })
        }
      } catch (e) { /* network not ready */ }
    }

    // Draw orbiting particles around nodes
    for (const node of nodePositions) {
      if (!isFinite(node.x) || !isFinite(node.y)) continue

      // Outer glow pulse
      const pulse = 1 + Math.sin(time * 2 + node.x * 0.01) * 0.15
      const glowRadius = node.size * pulse
      const hoverBoost = node.isHovered ? 2.5 : 1

      // Multi-layer glow
      for (let layer = 2; layer >= 0; layer--) {
        const layerRadius = glowRadius * (1.8 + layer * 0.8) * hoverBoost
        const gradient = ctx.createRadialGradient(node.x, node.y, 0, node.x, node.y, layerRadius)
        gradient.addColorStop(0, `rgba(${hexToRgb(node.color)}, ${0.25 * hoverBoost})`)
        gradient.addColorStop(0.5, `rgba(${hexToRgb(node.color)}, ${0.08 * hoverBoost})`)
        gradient.addColorStop(1, 'rgba(0, 0, 0, 0)')
        ctx.beginPath()
        ctx.arc(node.x, node.y, layerRadius, 0, Math.PI * 2)
        ctx.fillStyle = gradient
        ctx.fill()
      }

      // Orbiting particles (only for larger/important nodes or hovered)
      if (node.size > 18 || node.isHovered) {
        const orbitCount = node.isHovered ? 5 : 3
        for (let o = 0; o < orbitCount; o++) {
          const orbitR = node.size * (1.8 + o * 0.6) * (node.isHovered ? 1.3 : 1)
          const orbitSpeed = 0.5 + o * 0.15
          const orbitPhase = time * orbitSpeed + o * 2.1 + node.x * 0.003
          const opx = node.x + Math.cos(orbitPhase) * orbitR
          const opy = node.y + Math.sin(orbitPhase) * orbitR

          ctx.beginPath()
          ctx.arc(opx, opy, node.isHovered ? 2.5 : 1.8, 0, Math.PI * 2)
          ctx.fillStyle = `rgba(${hexToRgb(node.color)}, ${0.6 + Math.sin(time * 3 + o) * 0.2})`
          ctx.fill()

          // Orbit trail arc
          ctx.beginPath()
          ctx.arc(node.x, node.y, orbitR, orbitPhase - 0.3, orbitPhase)
          ctx.strokeStyle = `rgba(${hexToRgb(node.color)}, 0.15)`
          ctx.lineWidth = 1
          ctx.stroke()
        }
      }
    }

    // Draw connection highlight (for hovered node)
    if (hoverNodeId !== null && nodePositions.length > 0) {
      const hovered = nodePositions.find(n => n.id === hoverNodeId)
      if (hovered) {
        const neighbors = adjacencyMap.value.get(hoverNodeId)
        if (neighbors) {
          for (const neighborId of neighbors) {
            const target = nodePositions.find(n => String(n.id) === String(neighborId) || n.id === neighborId)
            if (target) {
              // Flowing pulsing line from hovered node to its neighbors
              const dx = target.x - hovered.x
              const dy = target.y - hovered.y
              const dist = Math.sqrt(dx * dx + dy * dy)
              const steps = Math.min(8, Math.floor(dist / 30))

              for (let s = 0; s < steps; s++) {
                const t = ((time * 0.8 + s / steps) % 1)
                const px = hovered.x + dx * t
                const py = hovered.y + dy * t
                const particleOpacity = Math.sin(t * Math.PI) * 0.8

                ctx.beginPath()
                ctx.arc(px, py, 3, 0, Math.PI * 2)
                ctx.fillStyle = `rgba(${hexToRgb(target.color)}, ${particleOpacity})`
                ctx.fill()
              }

              // Enhanced connection line
              ctx.beginPath()
              ctx.moveTo(hovered.x, hovered.y)
              ctx.lineTo(target.x, target.y)
              const lineGrad = ctx.createLinearGradient(hovered.x, hovered.y, target.x, target.y)
              lineGrad.addColorStop(0, `rgba(${hexToRgb(hovered.color)}, 0.6)`)
              lineGrad.addColorStop(1, `rgba(${hexToRgb(target.color)}, 0.6)`)
              ctx.strokeStyle = lineGrad
              ctx.lineWidth = 2
              ctx.stroke()
            }
          }
        }
      }
    }

    // Free floating particles
    for (const p of freeParticles) {
      p.x += p.vx
      p.y += p.vy

      if (p.x < 0 || p.x > w) p.vx *= -1
      if (p.y < 0 || p.y > h) p.vy *= -1

      // Gentle attraction to center
      p.vx += (w / 2 - p.x) * 0.00001
      p.vy += (h / 2 - p.y) * 0.00001

      // Damping
      p.vx *= 0.999
      p.vy *= 0.999

      ctx.beginPath()
      ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2)
      const alpha = p.opacity + Math.sin(time * 2 + p.x * 0.01) * 0.1
      ctx.fillStyle = `rgba(${hexToRgb(p.color)}, ${alpha})`
      ctx.fill()
    }

    particlesAnimId = requestAnimationFrame(animate)
  }

  animate()

  onBeforeUnmount(() => {
    cancelAnimationFrame(particlesAnimId)
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
    return { color: '#5AC8FA', opacity: 0.4, hover: 'rgba(90, 200, 250, 0.8)' }
  if ((fromType === 'entity' && toType === 'source') || (fromType === 'source' && toType === 'entity'))
    return { color: '#34C759', opacity: 0.3, hover: 'rgba(52, 199, 89, 0.7)' }
  if ((fromType === 'concept' && toType === 'source') || (fromType === 'source' && toType === 'concept'))
    return { color: '#FF9500', opacity: 0.3, hover: 'rgba(255, 149, 0, 0.7)' }
  if ((fromType === 'synthesis' && toType === 'concept') || (fromType === 'concept' && toType === 'synthesis'))
    return { color: '#AF52DE', opacity: 0.4, hover: 'rgba(175, 82, 222, 0.8)' }
  if (fromType === 'synthesis' || toType === 'synthesis')
    return { color: '#AF52DE', opacity: 0.25, hover: 'rgba(175, 82, 222, 0.7)' }
  return { color: '#5AC8FA', opacity: 0.3, hover: 'rgba(90, 200, 250, 0.7)' }
}

function destroyNetwork() {
  if (network) {
    try { network.destroy() } catch (e) {}
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
      color: {
        background: cfg.bg,
        border: cfg.border,
        highlight: { background: '#FFFFFF', border: cfg.border },
        hover: { background: '#FFFFFF', border: cfg.border }
      },
      borderWidth: cfg.borderWidth,
      borderWidthSelected: cfg.borderWidth + 2,
      shape: 'circle',
      size: size,
      font: { color: '#1D1D1F', size: 11, face: 'Inter', strokeWidth: 0, multi: false },
      shadow: true,
      chosen: {
        node: function(values, id, selected, hovering) {
          values.shadow = true
          values.shadowColor = nodeTypeConfig[typeMap[id]]?.glow || 'rgba(0, 122, 255, 0.4)'
          values.shadowBlur = 20
        }
      }
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
        color: {
          color: ec.color,
          opacity: ec.opacity,
          highlight: ec.color,
          hover: ec.color
        },
        width: Math.min(3, Math.max(0.5, weight * 1.5)),
        smooth: { type: 'continuous', roundness: 0.55 },
        arrows: { to: { enabled: false } }
      })
    })
  }

  nodeTypeMap.value = typeMap
  adjacencyMap.value = adjMap
  nodeIndex.value = nIdx

  const options = {
    physics: {
      enabled: true,
      solver: 'barnesHut',
      barnesHut: {
        gravitationalConstant: -3000,
        centralGravity: 0.3,
        springLength: 200,
        springConstant: 0.04,
        damping: 0.09,
        avoidOverlap: 0.5
      },
      stabilization: {
        iterations: 300,
        updateInterval: 50,
        fit: true
      },
      timestep: 0.3
    },
    interaction: {
      hover: true,
      zoomView: true,
      dragView: true,
      dragNodes: true,
      navigationButtons: false,
      multiselect: false,
      tooltipDelay: 100,
      hideEdgesOnDrag: false,
      hideEdgesOnZoom: false
    },
    nodes: {
      shadow: {
        enabled: true,
        color: 'rgba(0, 0, 0, 0.15)',
        size: 8,
        x: 2,
        y: 4
      }
    },
    edges: {
      smooth: { type: 'continuous', roundness: 0.55 }
    }
  }

  network = new Network(graphContainerRef.value, { nodes, edges }, options)

  // Entrance animation: fit then gently release
  network.once('stabilized', function() {
    network.fit({ animation: { duration: 800, easingFunction: 'easeOutQuad' } })
    // Keep physics alive with gentle oscillation
    setTimeout(() => {
      if (network) {
        network.setOptions({ physics: { barnesHut: { gravitationalConstant: -2000, springConstant: 0.03, damping: 0.15 } } })
      }
    }, 1500)
  })

  network.on('hoverNode', function(params) {
    hoverNodeId = params.node
    network.canvas.body.container.style.cursor = 'pointer'
  })

  network.on('blurNode', function() {
    hoverNodeId = null
    network.canvas.body.container.style.cursor = 'grab'
  })

  network.on('click', function(params) {
    if (params.nodes.length > 0) {
      const nodeId = params.nodes[0]
      const nodeData = nIdx.get(nodeId)
      if (nodeData) {
        emit('node-click', nodeData)
        // Focus animation
        network.focus(nodeId, {
          scale: 1.4,
          animation: { duration: 600, easingFunction: 'easeInOutQuad' }
        })
      }
    }
  })

  // Double-click to zoom out
  network.on('doubleClick', function() {
    network.fit({ animation: { duration: 500, easingFunction: 'easeOutQuad' } })
  })
}

// ── Lifecycle ─────────────────────────────────────────────────
onMounted(() => {
  initStarfield()
  initParticles()
  if (props.graphData) {
    setTimeout(renderGraph, 100)
  }
})

watch(() => props.graphData, () => {
  if (props.graphData) {
    setTimeout(renderGraph, 50)
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
  background: linear-gradient(135deg, #F5F5F7 0%, #FAFAFA 50%, #F0F0F5 100%);
}

.starfield {
  position: absolute;
  inset: 0;
  z-index: 0;
  pointer-events: none;
}

.ambient-glow {
  position: absolute;
  inset: 0;
  z-index: 1;
  pointer-events: none;
  background:
    radial-gradient(ellipse at 20% 20%, rgba(90, 200, 250, 0.08) 0%, transparent 50%),
    radial-gradient(ellipse at 80% 80%, rgba(175, 82, 222, 0.06) 0%, transparent 50%),
    radial-gradient(ellipse at 50% 50%, rgba(0, 122, 255, 0.04) 0%, transparent 70%);
  animation: glowShift 20s ease-in-out infinite alternate;
}

@keyframes glowShift {
  0% { opacity: 0.7; transform: scale(1); }
  50% { opacity: 1; transform: scale(1.05); }
  100% { opacity: 0.8; transform: scale(1); }
}

.particles-overlay {
  position: absolute;
  inset: 0;
  z-index: 2;
  pointer-events: none;
}

.graph-container {
  position: absolute;
  inset: 0;
  z-index: 5;
  cursor: grab;
}

.graph-container:active {
  cursor: grabbing;
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
  animation: fadeInUp 600ms var(--ease-out-expo);
}

.stats-badge {
  position: absolute;
  top: 16px;
  right: 16px;
  z-index: 10;
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 14px;
  border-radius: var(--radius-sm);
  animation: fadeInDown 600ms var(--ease-out-expo);
}

.stat-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
}

.stat-num {
  font-size: 0.9375rem;
  font-weight: 700;
  color: var(--text-primary);
  letter-spacing: -0.02em;
}

.stat-label {
  font-size: 0.5625rem;
  color: var(--text-tertiary);
  text-transform: uppercase;
  letter-spacing: 0.08em;
}

.stat-divider {
  width: 1px;
  height: 24px;
  background: rgba(0, 0, 0, 0.08);
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
  box-shadow: 0 0 8px currentColor;
  animation: pulse 2s ease-in-out infinite;
}

@keyframes pulse {
  0%, 100% { transform: scale(1); opacity: 1; }
  50% { transform: scale(1.2); opacity: 0.8; }
}

.loading-overlay,
.empty-overlay {
  position: absolute;
  inset: 0;
  z-index: 20;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(245, 245, 247, 0.5);
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
}

.loading-card,
.empty-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
  padding: 36px 56px;
  border-radius: var(--radius-xl);
  animation: fadeInUp 500ms var(--ease-out-expo);
  text-align: center;
}

.spinner {
  position: relative;
  width: 56px;
  height: 56px;
}

.spinner-ring {
  position: absolute;
  inset: 0;
  border-radius: 50%;
  border: 2px solid transparent;
  border-top-color: #007AFF;
  border-right-color: #5AC8FA;
  border-bottom-color: #AF52DE;
  animation: spin 1.2s cubic-bezier(0.4, 0, 0.2, 1) infinite;
}

.spinner-core {
  position: absolute;
  inset: 16px;
  border-radius: 50%;
  background: radial-gradient(circle, #007AFF 0%, #5AC8FA 50%, transparent 70%);
  animation: corePulse 1.5s ease-in-out infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

@keyframes corePulse {
  0%, 100% { transform: scale(0.8); opacity: 0.6; }
  50% { transform: scale(1.1); opacity: 1; }
}

.empty-icon-ring {
  width: 72px;
  height: 72px;
  border-radius: 50%;
  background: linear-gradient(135deg, rgba(0, 122, 255, 0.08) 0%, rgba(175, 82, 222, 0.08) 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
}

.empty-icon-ring::before {
  content: '';
  position: absolute;
  inset: -4px;
  border-radius: 50%;
  border: 1px dashed rgba(0, 122, 255, 0.2);
  animation: spin 20s linear infinite;
}

.empty-icon-ring svg {
  width: 36px;
  height: 36px;
  color: #007AFF;
}

.empty-card p {
  font-size: 0.875rem;
  color: var(--text-secondary);
  margin: 0;
}

@keyframes fadeInUp {
  from {
    opacity: 0;
    transform: translateY(12px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@keyframes fadeInDown {
  from {
    opacity: 0;
    transform: translateY(-12px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}
</style>
