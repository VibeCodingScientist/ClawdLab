/**
 * WorkspaceMiniPreview -- Lightweight animated canvas showing a mini workspace preview.
 * Zone-colored rectangles + animated archetype-colored dots + "LIVE" badge.
 * Depends on: React, react-router-dom
 */
import { useRef, useEffect } from 'react'
import { Link } from 'react-router-dom'

const ZONES = [
  { x: 0, y: 0, w: 100, h: 80, color: '#FFD700' },    // PI Desk
  { x: 100, y: 0, w: 100, h: 80, color: '#FFA500' },   // Ideation
  { x: 200, y: 0, w: 100, h: 140, color: '#4169E1' },  // Library
  { x: 300, y: 0, w: 100, h: 140, color: '#9370DB' },  // Whiteboard
  { x: 0, y: 80, w: 200, h: 100, color: '#32CD32' },   // Bench
  { x: 120, y: 180, w: 160, h: 120, color: '#FF6347' }, // Roundtable
  { x: 280, y: 140, w: 120, h: 160, color: '#00CED1' }, // Presentation
  { x: 0, y: 180, w: 120, h: 120, color: '#8B4513' },  // Entrance
]

const AGENT_DOTS = [
  { color: '#F5C542', zone: 0 },  // pi
  { color: '#5B8DEF', zone: 3 },  // theorist
  { color: '#4ADE80', zone: 4 },  // experimentalist
  { color: '#EF6461', zone: 5 },  // critic
  { color: '#A78BFA', zone: 6 },  // synthesizer
  { color: '#22D3EE', zone: 2 },  // scout
  { color: '#C2956B', zone: 1 },  // mentor
  { color: '#D97706', zone: 4 },  // technician
]

interface WorkspaceMiniPreviewProps {
  slug: string
  className?: string
}

export function WorkspaceMiniPreview({ slug, className }: WorkspaceMiniPreviewProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const frameRef = useRef(0)

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    let running = true

    function draw() {
      if (!running || !ctx) return
      const frame = frameRef.current++

      // Background
      ctx.fillStyle = '#1a1a2e'
      ctx.fillRect(0, 0, 400, 300)

      // Zones
      for (const zone of ZONES) {
        ctx.fillStyle = zone.color
        ctx.globalAlpha = 0.12
        ctx.fillRect(zone.x, zone.y, zone.w, zone.h)
        ctx.globalAlpha = 0.25
        ctx.strokeStyle = zone.color
        ctx.lineWidth = 0.5
        ctx.strokeRect(zone.x, zone.y, zone.w, zone.h)
      }
      ctx.globalAlpha = 1

      // Animated agent dots
      for (let i = 0; i < AGENT_DOTS.length; i++) {
        const dot = AGENT_DOTS[i]
        const zone = ZONES[dot.zone]
        // Agent wanders slowly within its zone
        const t = (frame + i * 60) * 0.01
        const dx = Math.sin(t * 1.3 + i) * (zone.w * 0.3)
        const dy = Math.cos(t * 0.9 + i * 2) * (zone.h * 0.3)
        const cx = zone.x + zone.w / 2 + dx
        const cy = zone.y + zone.h / 2 + dy

        // Glow
        ctx.fillStyle = dot.color
        ctx.globalAlpha = 0.2
        ctx.beginPath()
        ctx.arc(cx, cy, 6, 0, Math.PI * 2)
        ctx.fill()

        // Dot
        ctx.globalAlpha = 0.9
        ctx.beginPath()
        ctx.arc(cx, cy, 3, 0, Math.PI * 2)
        ctx.fill()
      }
      ctx.globalAlpha = 1

      requestAnimationFrame(draw)
    }

    draw()

    return () => {
      running = false
    }
  }, [])

  return (
    <Link to={`/labs/${slug}/workspace`} className={`block relative ${className ?? ''}`}>
      <canvas
        ref={canvasRef}
        width={400}
        height={300}
        className="w-full rounded-lg border border-border/50"
        style={{ imageRendering: 'auto' }}
      />
      {/* LIVE badge */}
      <span className="absolute top-2 right-2 flex items-center gap-1.5 rounded-full bg-red-600/90 px-2 py-0.5 text-[10px] font-bold text-white uppercase tracking-wider">
        <span className="h-1.5 w-1.5 rounded-full bg-white animate-pulse" />
        Live
      </span>
    </Link>
  )
}
