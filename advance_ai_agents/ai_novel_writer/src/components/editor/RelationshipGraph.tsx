import { useRef, useEffect } from 'react'

interface CharacterNode {
  name: string
  role: string
  x: number
  y: number
  vx: number
  vy: number
}

interface RelationshipEdge {
  from: string
  to: string
  label: string
}

interface RelationshipGraphProps {
  characters: Array<{
    name: string
    role: string
    relationships: string
  }>
}

/** 从角色关系文本中解析出关系边 */
function parseRelationships(characters: RelationshipGraphProps['characters']): RelationshipEdge[] {
  const edges: RelationshipEdge[] = []

  for (const char of characters) {
    if (!char.relationships) continue
    // 尝试多种格式：JSON 数组 / "名字：关系" / "名字 - 关系"
    try {
      const parsed = JSON.parse(char.relationships)
      if (Array.isArray(parsed)) {
        for (const rel of parsed) {
          const targetName = rel.name || rel.target
          if (targetName && characters.some(c => c.name === targetName)) {
            edges.push({ from: char.name, to: targetName, label: rel.relation || rel.label || '' })
          }
        }
        continue
      }
    } catch { /* 不是 JSON，继续用文本解析 */ }

    // 文本格式解析
    const lines = char.relationships.split(/[,;，；\n]/).filter(Boolean)
    for (const line of lines) {
      const match = line.match(/(.+?)[：:—-]\s*(.+)/)
      if (match) {
        const targetName = match[1].trim()
        const label = match[2].trim()
        if (characters.some(c => c.name === targetName)) {
          edges.push({ from: char.name, to: targetName, label })
        }
      }
    }
  }

  return edges
}

const ROLE_COLORS: Record<string, string> = {
  protagonist: '#6ee7b7',
  antagonist: '#fca5a5',
  supporting: '#93c5fd',
  minor: '#a78bfa',
}

/** 角色关系网 Canvas 可视化 */
export default function RelationshipGraph({ characters }: RelationshipGraphProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const nodesRef = useRef<CharacterNode[]>([])
  const animRef = useRef<number>(0)

  const edges = parseRelationships(characters)

  // 初始化节点布局
  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return

    const w = canvas.offsetWidth
    const h = canvas.offsetHeight
    canvas.width = w * 2
    canvas.height = h * 2

    const centerX = w
    const centerY = h
    const radius = Math.min(w, h) * 0.6

    // 环形初始布局
    nodesRef.current = characters.map((c, i) => {
      const angle = (i / characters.length) * Math.PI * 2 - Math.PI / 2
      return {
        name: c.name,
        role: c.role,
        x: centerX + radius * Math.cos(angle),
        y: centerY + radius * Math.sin(angle),
        vx: 0,
        vy: 0,
      }
    })

    // 启动力导向模拟
    let iteration = 0
    const maxIterations = 120

    const drawFrame = () => {
      const canvas = canvasRef.current
      if (!canvas) return
      const ctx = canvas.getContext('2d')
      if (!ctx) return

      const nodes = nodesRef.current

      ctx.clearRect(0, 0, canvas.width, canvas.height)

      // 绘制连线
      ctx.lineWidth = 1.5
      for (const edge of edges) {
        const a = nodes.find((n) => n.name === edge.from)
        const b = nodes.find((n) => n.name === edge.to)
        if (!a || !b) continue

        ctx.beginPath()
        ctx.moveTo(a.x, a.y)
        ctx.lineTo(b.x, b.y)
        ctx.strokeStyle = 'rgba(148,163,184,0.3)'
        ctx.stroke()

        // 关系标签
        if (edge.label) {
          const mx = (a.x + b.x) / 2
          const my = (a.y + b.y) / 2
          ctx.font = '18px system-ui'
          ctx.fillStyle = 'rgba(148,163,184,0.6)'
          ctx.textAlign = 'center'
          ctx.fillText(edge.label, mx, my - 4)
        }
      }

      // 绘制节点
      for (const node of nodes) {
        const color = ROLE_COLORS[node.role] || '#94a3b8'

        // 光晕
        ctx.beginPath()
        ctx.arc(node.x, node.y, 28, 0, Math.PI * 2)
        ctx.fillStyle = color + '25'
        ctx.fill()

        // 节点
        ctx.beginPath()
        ctx.arc(node.x, node.y, 20, 0, Math.PI * 2)
        ctx.fillStyle = color + '40'
        ctx.fill()
        ctx.strokeStyle = color
        ctx.lineWidth = 2
        ctx.stroke()

        // 名字
        ctx.font = 'bold 22px system-ui'
        ctx.fillStyle = color
        ctx.textAlign = 'center'
        ctx.textBaseline = 'middle'
        ctx.fillText(node.name, node.x, node.y + 36)
      }
    }

    const simulate = () => {
      const nodes = nodesRef.current
      if (iteration >= maxIterations) {
        drawFrame()
        return
      }

      // 斥力（节点间）
      for (let i = 0; i < nodes.length; i++) {
        for (let j = i + 1; j < nodes.length; j++) {
          const dx = nodes[j].x - nodes[i].x
          const dy = nodes[j].y - nodes[i].y
          const dist = Math.max(Math.sqrt(dx * dx + dy * dy), 1)
          const force = 8000 / (dist * dist)
          const fx = (dx / dist) * force
          const fy = (dy / dist) * force
          nodes[i].vx -= fx
          nodes[i].vy -= fy
          nodes[j].vx += fx
          nodes[j].vy += fy
        }
      }

      // 引力（连线间）
      for (const edge of edges) {
        const a = nodes.find((n) => n.name === edge.from)
        const b = nodes.find((n) => n.name === edge.to)
        if (!a || !b) continue
        const dx = b.x - a.x
        const dy = b.y - a.y
        const dist = Math.sqrt(dx * dx + dy * dy)
        const force = (dist - 150) * 0.01
        const fx = (dx / dist) * force
        const fy = (dy / dist) * force
        a.vx += fx
        a.vy += fy
        b.vx -= fx
        b.vy -= fy
      }

      // 向心力
      for (const node of nodes) {
        node.vx += (centerX - node.x) * 0.002
        node.vy += (centerY - node.y) * 0.002
      }

      // 应用速度 + 阻尼
      const damping = 0.85
      for (const node of nodes) {
        node.vx *= damping
        node.vy *= damping
        node.x += node.vx
        node.y += node.vy
        // 边界约束
        node.x = Math.max(40, Math.min(w * 2 - 40, node.x))
        node.y = Math.max(40, Math.min(h * 2 - 40, node.y))
      }

      iteration++
      drawFrame()
      animRef.current = requestAnimationFrame(simulate)
    }

    simulate()

    return () => cancelAnimationFrame(animRef.current)
  }, [characters, edges])

  if (characters.length === 0) {
    return (
      <div className="flex items-center justify-center h-full text-xs text-[var(--color-text-muted)]">
        暂无角色数据
      </div>
    )
  }

  return (
    <canvas
      ref={canvasRef}
      className="w-full h-full"
      style={{ background: 'transparent' }}
    />
  )
}
