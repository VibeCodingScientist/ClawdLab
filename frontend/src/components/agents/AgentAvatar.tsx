/**
 * AgentAvatar -- React canvas component that draws a front-facing pixel-art agent sprite.
 * Uses archetype colors from ARCHETYPE_CONFIGS and drawing helpers from colorUtils.
 * Depends on: React, ARCHETYPE_CONFIGS, colorUtils
 */
import { useRef, useEffect } from 'react'
import { ARCHETYPE_CONFIGS } from '@/workspace/game/config/archetypes'
import type { RoleArchetype } from '@/workspace/game/config/archetypes'
import { darken, lighten, px, hline, vline } from '@/workspace/game/art/colorUtils'

interface AgentAvatarProps {
  archetype: RoleArchetype | string
  /** Pixel scale multiplier (default 2 → 32x32) */
  scale?: number
  className?: string
}

export function AgentAvatar({ archetype, scale = 2, className }: AgentAvatarProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const config = ARCHETYPE_CONFIGS[archetype as RoleArchetype] ?? ARCHETYPE_CONFIGS.generalist

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    ctx.clearRect(0, 0, 16, 16)

    const color = config.color
    const shirtColor = color
    const pantsColor = darken(color, 0.25)
    const shoeColor = darken(color, 0.5)
    const armColor = darken(color, 0.1)
    const skinTone = config.skinTone
    const skinHighlight = lighten(skinTone, 0.12)
    const skinShadow = darken(skinTone, 0.15)
    const hairColor = config.hairColor
    const hairHighlight = lighten(hairColor, 0.20)
    const eyeColor = config.eyeColor
    const headOutline = darken(hairColor, 0.50)
    const bodyOutline = darken(shirtColor, 0.50)
    const shoeOutline = darken(shoeColor, 0.30)

    const bob = 0 // idle frame
    const c = ctx

    // Ground shadow
    c.fillStyle = 'rgba(0,0,0,0.12)'
    c.fillRect(5, 13, 6, 1)
    c.fillStyle = 'rgba(0,0,0,0.20)'
    c.fillRect(4, 14, 8, 1)
    c.fillStyle = 'rgba(0,0,0,0.10)'
    c.fillRect(3, 15, 10, 1)

    // Shirt
    c.fillStyle = shirtColor
    c.fillRect(4, 5 + bob, 8, 4)
    px(c, 7, 5 + bob, '#EEEEEE')
    px(c, 8, 5 + bob, '#EEEEEE')
    vline(c, 5, 6 + bob, 3, darken(shirtColor, 0.15))
    px(c, 8, 6 + bob, darken(shirtColor, 0.20))
    px(c, 8, 7 + bob, darken(shirtColor, 0.20))
    hline(c, 5, 8 + bob, 6, darken(shirtColor, 0.30))

    // Pants
    c.fillStyle = pantsColor
    c.fillRect(4, 9 + bob, 8, 3)
    vline(c, 8, 9 + bob, 3, darken(pantsColor, 0.12))
    px(c, 6, 9 + bob, darken(pantsColor, 0.20))
    px(c, 10, 9 + bob, darken(pantsColor, 0.20))

    // Arms
    c.fillStyle = armColor
    c.fillRect(3, 6 + bob, 1, 4)
    c.fillRect(12, 6 + bob, 1, 4)
    px(c, 3, 9 + bob, skinTone)
    px(c, 12, 9 + bob, skinTone)

    // Head
    c.fillStyle = skinTone
    c.fillRect(5, 1 + bob, 6, 5)
    hline(c, 6, 1 + bob, 4, skinHighlight)
    px(c, 10, 2 + bob, skinShadow)
    px(c, 10, 3 + bob, skinShadow)
    px(c, 10, 4 + bob, skinShadow)
    px(c, 9, 3 + bob, skinShadow)
    px(c, 9, 4 + bob, skinShadow)
    hline(c, 6, 5 + bob, 4, skinShadow)
    c.clearRect(5, 1 + bob, 1, 1)
    c.clearRect(10, 1 + bob, 1, 1)
    c.clearRect(5, 5 + bob, 1, 1)
    c.clearRect(10, 5 + bob, 1, 1)

    // Hair
    px(c, 6, 1 + bob, hairColor)
    hline(c, 7, 1 + bob, 2, hairHighlight)
    px(c, 9, 1 + bob, hairColor)
    px(c, 5, 2 + bob, darken(hairColor, 0.20))
    hline(c, 6, 2 + bob, 4, hairColor)
    px(c, 10, 2 + bob, darken(hairColor, 0.20))
    px(c, 5, 3 + bob, hairColor)
    px(c, 10, 2 + bob, hairColor)

    // Eyes (front-facing)
    c.fillStyle = '#ffffff'
    c.fillRect(6, 3 + bob, 2, 2)
    c.fillRect(9, 3 + bob, 2, 2)
    px(c, 7, 3 + bob, eyeColor)
    px(c, 10, 3 + bob, eyeColor)
    px(c, 7, 4 + bob, '#111111')
    px(c, 10, 4 + bob, '#111111')
    px(c, 6, 2 + bob, darken(skinTone, 0.20))
    px(c, 9, 2 + bob, darken(skinTone, 0.20))
    px(c, 6, 4 + bob, '#E8A0A0')
    px(c, 9, 4 + bob, '#E8A0A0')
    px(c, 8, 4 + bob, skinShadow)

    // Legs + shoes (idle frame 0)
    c.fillStyle = pantsColor
    c.fillRect(5, 12 + bob, 3, 2)
    c.fillRect(9, 12 + bob, 3, 2)
    c.fillStyle = shoeColor
    c.fillRect(5, 14 + bob, 3, 1)
    c.fillRect(9, 14 + bob, 3, 1)

    // Outlines
    hline(c, 6, bob, 4, headOutline)
    vline(c, 2, 6 + bob, 4, bodyOutline)
    vline(c, 13, 6 + bob, 4, bodyOutline)
    hline(c, 5, 15 + bob, 3, shoeOutline)
    hline(c, 9, 15 + bob, 3, shoeOutline)
  }, [config])

  const size = 16 * scale

  return (
    <canvas
      ref={canvasRef}
      width={16}
      height={16}
      className={className}
      style={{
        width: size,
        height: size,
        imageRendering: 'pixelated',
      }}
    />
  )
}
