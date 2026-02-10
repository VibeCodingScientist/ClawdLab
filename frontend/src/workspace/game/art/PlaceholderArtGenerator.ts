/**
 * PlaceholderArtGenerator -- Generates canvas-based pixel art textures for tiles, agents, and UI elements.
 * Full Stardew Valley style: wood plank floors, rounded stone walls, material textures,
 * 3-shade character rendering with colored outlines.
 * Depends on: Phaser, ARCHETYPE_CONFIGS
 */
import Phaser from 'phaser'
import { ARCHETYPE_CONFIGS, type RoleArchetype } from '../config/archetypes'
import { darken, lighten, px, hline, vline } from './colorUtils'

// ─── Color helpers ───────────────────────────────────────────────────────────

/** Checkerboard dither fill for SDV gradient transitions */
function dither(ctx: CanvasRenderingContext2D, x: number, y: number, w: number, h: number, colorA: string, colorB: string): void {
  for (let dy = 0; dy < h; dy++) {
    for (let dx = 0; dx < w; dx++) {
      ctx.fillStyle = ((dx + dy) % 2 === 0) ? colorA : colorB
      ctx.fillRect(x + dx, y + dy, 1, 1)
    }
  }
}

// ─── Tile rendering ──────────────────────────────────────────────────────────

export class PlaceholderArtGenerator {
  static generateTileset(scene: Phaser.Scene): void {
    const canvas = document.createElement('canvas')
    canvas.width = 256
    canvas.height = 16
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    const drawTile: Array<(ctx: CanvasRenderingContext2D) => void> = [
      // ── 0: Floor — Clean Lab Tile ──
      (c) => {
        const tileBase = '#3C3E44'
        const tileLighter = '#42444A'
        c.fillStyle = tileBase
        c.fillRect(0, 0, 16, 16)

        // Subtle speckle noise for linoleum texture
        const speckles = ['#3A3C42', '#40424A', '#3E4048', '#444650']
        for (let y = 0; y < 16; y++) {
          for (let x = 0; x < 16; x++) {
            const hash = (x * 7 + y * 13 + x * y) % 4
            if (hash === 0) px(c, x, y, speckles[(x + y) % speckles.length])
          }
        }

        // Grout lines (right + bottom edges) — thin grey grid
        hline(c, 0, 15, 16, '#32343A')
        vline(c, 15, 0, 16, '#32343A')
        // Top/left bevel highlight
        hline(c, 0, 0, 16, tileLighter)
        vline(c, 0, 0, 16, tileLighter)

        // Occasional floor sparkle (clean wax reflection)
        px(c, 4, 6, '#4A4C52')
        px(c, 11, 3, '#4A4C52')
        px(c, 7, 12, '#4A4C52')
      },

      // ── 1: Wall — Clean Lab Wall with Baseboard ──
      (c) => {
        const wallBase = '#2A2C32'
        const wallLight = '#303238'
        const baseboard = '#222428'

        // Painted wall fill
        c.fillStyle = wallBase
        c.fillRect(0, 0, 16, 16)

        // Subtle vertical texture (painted drywall)
        for (let x = 0; x < 16; x += 3) {
          vline(c, x, 0, 14, wallLight)
        }

        // Top lit edge (overhead fluorescent reflection)
        hline(c, 0, 0, 16, '#383A42')
        hline(c, 0, 1, 16, '#343640')

        // Baseboard (bottom 2px, darker trim)
        hline(c, 0, 14, 16, baseboard)
        hline(c, 0, 15, 16, darken(baseboard, 0.15))

        // Baseboard highlight line
        hline(c, 0, 13, 16, '#2E3036')

        // Occasional wall detail (outlet plate, scuff mark)
        px(c, 8, 8, '#252730')
        px(c, 9, 8, '#252730')
        px(c, 8, 9, '#252730')
        px(c, 9, 9, '#252730')
      },

      // ── 2: Bookshelf — Wood grain + colored outline ──
      (c) => {
        const frame = '#4a3728'
        const frameOutline = '#2A1A0C'
        const shelfLight = '#6a5748'
        const dark = '#3a2718'
        c.fillStyle = frame
        c.fillRect(0, 0, 16, 16)

        // Vertical wood grain
        for (let gx = 2; gx < 15; gx += 3) {
          vline(c, gx, 0, 16, darken(frame, 0.08))
        }
        // Knot hole
        px(c, 8, 0, darken(frame, 0.25))
        px(c, 9, 0, darken(frame, 0.20))

        // Frame edges (colored outline)
        vline(c, 0, 0, 16, frameOutline)
        vline(c, 15, 0, 16, frameOutline)
        hline(c, 0, 0, 16, lighten(frame, 0.15))
        hline(c, 0, 15, 16, frameOutline)

        // Three shelves with dithered transitions
        const shelfYs = [4, 9, 14]
        for (const sy of shelfYs) {
          hline(c, 1, sy, 14, shelfLight)
          dither(c, 1, sy + 1, 14, 1, dark, darken(dark, 0.1))
        }

        // Book spines
        const bookColors = ['#c44444', '#4444cc', '#44aa44', '#ccaa44', '#cc6644', '#8844aa', '#44aacc', '#cc4488']
        let bi = 0
        for (let s = 0; s < 3; s++) {
          const startY = (s === 0) ? 1 : shelfYs[s - 1] + 2
          const endY = shelfYs[s]
          for (let bx = 1; bx < 15; bx += 2) {
            const bColor = bookColors[bi % bookColors.length]
            c.fillStyle = bColor
            c.fillRect(bx, startY, 1, endY - startY)
            c.fillStyle = darken(bColor, 0.15)
            c.fillRect(bx + 1, startY, 1, endY - startY)
            px(c, bx, startY, lighten(bColor, 0.25))
            bi++
          }
        }

        // Directional shadow
        vline(c, 15, 0, 16, 'rgba(0,0,0,0.2)')
        hline(c, 0, 14, 16, 'rgba(0,0,0,0.25)')
        hline(c, 0, 15, 16, 'rgba(0,0,0,0.25)')
      },

      // ── 3: Lab Bench — Anisotropic metal (5 shade bands) ──
      (c) => {
        const shades = ['#4A4A5B', '#505066', '#5A5A6B', '#636374', '#6A6A7B']
        // 5 horizontal shade bands for anisotropic metal
        for (let row = 0; row < 16; row++) {
          const band = Math.min(4, Math.floor(row / 3))
          c.fillStyle = shades[band]
          c.fillRect(0, row, 16, 1)
        }
        // Specular highlight band at row 2
        hline(c, 0, 2, 16, lighten(shades[0], 0.2))
        hline(c, 0, 3, 16, lighten(shades[1], 0.15))

        // Screw dots at corners
        px(c, 1, 1, '#333344')
        px(c, 14, 1, '#333344')
        px(c, 1, 14, '#333344')
        px(c, 14, 14, '#333344')

        // Flask with glass effect (left side)
        c.fillStyle = 'rgba(136,204,255,0.5)'
        px(c, 3, 3, 'rgba(136,204,255,0.5)'); px(c, 4, 3, 'rgba(136,204,255,0.5)')
        px(c, 3, 4, 'rgba(136,204,255,0.5)'); px(c, 4, 4, 'rgba(136,204,255,0.5)')
        px(c, 2, 5, 'rgba(102,153,204,0.6)'); px(c, 5, 5, 'rgba(102,153,204,0.6)')
        c.fillStyle = 'rgba(136,204,255,0.5)'
        c.fillRect(2, 6, 4, 1)
        c.fillStyle = 'rgba(170,221,255,0.4)'
        c.fillRect(1, 7, 6, 1)
        // Specular white dot
        px(c, 3, 3, '#ffffff')
        // Flask bottom
        c.fillStyle = 'rgba(102,153,204,0.6)'
        c.fillRect(1, 8, 6, 1)

        // Test tube rack (right)
        c.fillStyle = '#777788'
        c.fillRect(9, 4, 6, 1)
        c.fillRect(9, 9, 6, 1)
        const tubeColors = ['#ff6666', '#66ff66', '#6666ff']
        for (let t = 0; t < 3; t++) {
          const tx = 10 + t * 2
          vline(c, tx, 5, 4, '#aaaabb')
          px(c, tx, 7, tubeColors[t])
          px(c, tx, 8, tubeColors[t])
        }

        // Bottom edge shadow
        hline(c, 0, 15, 16, '#444455')
        vline(c, 15, 0, 16, 'rgba(0,0,0,0.2)')
        hline(c, 0, 14, 16, 'rgba(0,0,0,0.2)')
      },

      // ── 4: Terminal — Phosphor dither screen ──
      (c) => {
        const bezel = '#0A0A1A'
        c.fillStyle = '#222233'
        c.fillRect(0, 0, 16, 16)

        // Monitor body with colored bezel outline
        c.fillStyle = '#111122'
        c.fillRect(1, 0, 14, 11)
        hline(c, 0, 0, 16, bezel)
        vline(c, 0, 0, 11, bezel)
        vline(c, 15, 0, 11, bezel)
        hline(c, 1, 10, 14, bezel)

        // Rounded inner screen
        c.fillStyle = '#003322'
        c.fillRect(2, 1, 12, 9)
        px(c, 2, 1, '#111122'); px(c, 13, 1, '#111122')
        px(c, 2, 9, '#111122'); px(c, 13, 9, '#111122')

        // Green screen with dithered edge
        c.fillStyle = '#00aa55'
        c.fillRect(3, 2, 10, 7)
        // Dithered screen-to-bezel transition
        dither(c, 2, 2, 1, 7, '#003322', '#005533')
        dither(c, 13, 2, 1, 7, '#003322', '#005533')

        // 3 code lines
        hline(c, 4, 3, 6, '#00ff88')
        hline(c, 4, 5, 4, '#00dd66')
        hline(c, 4, 7, 7, '#00cc55')

        // CRT scanlines
        for (let sy = 2; sy < 9; sy += 2) {
          c.fillStyle = 'rgba(0,255,100,0.08)'
          c.fillRect(3, sy, 10, 1)
        }

        // Screen highlight arc
        c.fillStyle = 'rgba(255,255,255,0.1)'
        c.fillRect(4, 2, 8, 1)

        // Keyboard
        c.fillStyle = '#333344'
        c.fillRect(3, 12, 10, 2)
        for (let kx = 4; kx < 12; kx += 2) {
          px(c, kx, 12, '#4a4a5b')
          px(c, kx, 13, '#3a3a4b')
        }

        // Stand
        c.fillStyle = '#1a1816'
        c.fillRect(6, 14, 4, 2)

        vline(c, 15, 0, 16, 'rgba(0,0,0,0.2)')
        hline(c, 0, 14, 16, 'rgba(0,0,0,0.2)')
        hline(c, 0, 15, 16, 'rgba(0,0,0,0.25)')
      },

      // ── 5: Whiteboard — Brushed aluminum frame ──
      (c) => {
        const frame = '#555566'
        c.fillStyle = frame
        c.fillRect(0, 0, 16, 16)
        // Brushed aluminum frame: cross-hatch
        for (let fy = 0; fy < 16; fy += 2) {
          hline(c, 0, fy, 16, lighten(frame, 0.06))
        }

        // White surface
        c.fillStyle = '#eeeef4'
        c.fillRect(1, 1, 14, 12)
        // Cross-hatch surface texture
        for (let ty = 2; ty < 12; ty += 3) {
          for (let tx = 2; tx < 14; tx += 3) {
            px(c, tx, ty, '#e4e4ea')
          }
        }

        // Marker diagram
        px(c, 4, 4, '#4466cc'); px(c, 5, 3, '#4466cc'); px(c, 6, 4, '#4466cc'); px(c, 5, 5, '#4466cc')
        px(c, 10, 4, '#cc4444'); px(c, 11, 3, '#cc4444'); px(c, 12, 4, '#cc4444'); px(c, 11, 5, '#cc4444')
        hline(c, 6, 4, 4, '#888899')
        px(c, 7, 9, '#44aa44'); px(c, 8, 8, '#44aa44'); px(c, 9, 9, '#44aa44'); px(c, 8, 10, '#44aa44')
        vline(c, 5, 5, 3, '#888899')
        hline(c, 5, 8, 3, '#888899')
        vline(c, 11, 5, 3, '#888899')
        hline(c, 9, 8, 2, '#888899')

        // Eraser smudge
        c.fillStyle = 'rgba(200,200,210,0.5)'
        c.fillRect(3, 10, 3, 2)

        // Marker tray at bottom
        c.fillStyle = '#444455'
        c.fillRect(1, 13, 14, 1)
        // 3 colored markers in tray
        px(c, 4, 13, '#cc3333'); px(c, 5, 13, '#cc3333')
        px(c, 7, 13, '#3333cc'); px(c, 8, 13, '#3333cc')
        px(c, 10, 13, '#33aa33'); px(c, 11, 13, '#33aa33')

        // Frame shadow
        hline(c, 0, 15, 16, darken(frame, 0.2))
        hline(c, 0, 0, 16, lighten(frame, 0.15))
        vline(c, 15, 0, 16, 'rgba(0,0,0,0.2)')
        hline(c, 0, 14, 16, 'rgba(0,0,0,0.2)')
      },

      // ── 6: Round Table — Rich wood with full perimeter darkening ──
      (c) => {
        const bg = '#44403a'
        c.fillStyle = bg
        c.fillRect(0, 0, 16, 16)

        const wood = '#9B7924'
        const woodDark = '#7B5904'
        const woodLight = '#B89934'

        const circlePixels = [
          [0,0,0,0,0,1,1,1,1,1,1,0,0,0,0,0],
          [0,0,0,1,1,1,1,1,1,1,1,1,1,0,0,0],
          [0,0,1,1,1,1,1,1,1,1,1,1,1,1,0,0],
          [0,1,1,1,1,1,1,1,1,1,1,1,1,1,1,0],
          [0,1,1,1,1,1,1,1,1,1,1,1,1,1,1,0],
          [1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1],
          [1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1],
          [1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1],
          [1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1],
          [1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1],
          [0,1,1,1,1,1,1,1,1,1,1,1,1,1,1,0],
          [0,1,1,1,1,1,1,1,1,1,1,1,1,1,1,0],
          [0,0,1,1,1,1,1,1,1,1,1,1,1,1,0,0],
          [0,0,0,1,1,1,1,1,1,1,1,1,1,0,0,0],
          [0,0,0,0,0,1,1,1,1,1,1,0,0,0,0,0],
          [0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0],
        ]
        for (let y = 0; y < 16; y++) {
          for (let x = 0; x < 16; x++) {
            if (circlePixels[y][x]) {
              c.fillStyle = wood
              c.fillRect(x, y, 1, 1)
            }
          }
        }

        // 3px highlight arc (upper quadrant)
        const hlPixels: [number, number][] = [[5,1],[6,1],[7,1],[8,1],[3,3],[4,2],[5,2],[2,4],[3,4],[2,5],[3,5]]
        for (const [hx, hy] of hlPixels) {
          px(c, hx, hy, woodLight)
        }

        // Full perimeter darkening
        for (let y = 0; y < 15; y++) {
          for (let x = 0; x < 16; x++) {
            if (!circlePixels[y][x]) continue
            // Check if edge pixel
            const up = y > 0 ? circlePixels[y - 1][x] : 0
            const down = y < 14 ? circlePixels[y + 1][x] : 0
            const left = x > 0 ? circlePixels[y][x - 1] : 0
            const right = x < 15 ? circlePixels[y][x + 1] : 0
            if (!up || !down || !left || !right) {
              px(c, x, y, woodDark)
            }
          }
        }

        // Center mark cross
        px(c, 7, 7, darken(wood, 0.15)); px(c, 8, 7, darken(wood, 0.15))
        px(c, 7, 8, darken(wood, 0.15)); px(c, 8, 8, darken(wood, 0.15))

        // Wood grain
        c.fillStyle = 'rgba(0,0,0,0.06)'
        for (let gy = 2; gy < 14; gy += 2) {
          c.fillRect(3, gy, 10, 1)
        }

        vline(c, 15, 0, 16, 'rgba(0,0,0,0.2)')
        hline(c, 0, 14, 16, 'rgba(0,0,0,0.25)')
        hline(c, 0, 15, 16, 'rgba(0,0,0,0.25)')
      },

      // ── 7: Chair — Fabric cross-hatch ──
      (c) => {
        const bg = '#44403a'
        const seat = '#4a4440'
        const seatLight = '#5a5450'
        const seatDark = '#3a3430'
        const leg = '#333030'
        const legLight = '#444040'
        const outline = '#1E1C18'
        c.fillStyle = bg
        c.fillRect(0, 0, 16, 16)

        // Back rest (curved) with dithered texture
        dither(c, 5, 1, 6, 2, seatLight, seat)
        px(c, 4, 2, seatLight)
        px(c, 11, 2, seatLight)
        c.fillStyle = seat
        c.fillRect(5, 3, 6, 2)
        px(c, 4, 3, seat)
        px(c, 11, 3, seat)
        hline(c, 5, 1, 6, lighten(seat, 0.2))

        // Seat cushion with cross-hatch dither
        dither(c, 3, 6, 10, 3, seat, seatLight)
        hline(c, 3, 6, 10, seatLight)
        hline(c, 3, 8, 10, seatDark)

        // Armrests
        c.fillStyle = seatDark
        c.fillRect(2, 5, 2, 3)
        c.fillRect(12, 5, 2, 3)

        // 2-shade cylindrical legs
        vline(c, 4, 9, 5, leg)
        px(c, 5, 9, legLight); px(c, 5, 10, legLight); px(c, 5, 11, legLight)
        vline(c, 11, 9, 5, leg)
        px(c, 10, 9, legLight); px(c, 10, 10, legLight); px(c, 10, 11, legLight)

        // Leg base
        hline(c, 3, 14, 3, leg)
        hline(c, 10, 14, 3, leg)

        // Colored outline
        vline(c, 2, 1, 13, outline)
        vline(c, 13, 1, 13, outline)
        hline(c, 5, 0, 6, outline)

        vline(c, 15, 0, 16, 'rgba(0,0,0,0.2)')
        hline(c, 0, 14, 16, 'rgba(0,0,0,0.25)')
        hline(c, 0, 15, 16, 'rgba(0,0,0,0.25)')
      },

      // ── 8: Coffee Machine — Metal vs ceramic ──
      (c) => {
        const bg = '#333344'
        const body = '#444455'
        c.fillStyle = bg
        c.fillRect(0, 0, 16, 16)

        // Machine body with streaked texture
        for (let row = 1; row < 10; row++) {
          const shade = row % 3 === 0 ? lighten(body, 0.06) : (row % 3 === 1 ? body : darken(body, 0.04))
          c.fillStyle = shade
          c.fillRect(2, row, 12, 1)
        }
        hline(c, 2, 1, 12, lighten(body, 0.15))
        hline(c, 2, 9, 12, darken(body, 0.15))

        // Drip nozzle
        c.fillStyle = '#555566'
        c.fillRect(7, 7, 2, 3)

        // LED
        px(c, 12, 3, '#44ff44')
        px(c, 12, 5, '#ff4444')

        // Glass reservoir with dither
        dither(c, 3, 2, 3, 6, 'rgba(100,180,255,0.3)', 'rgba(80,160,235,0.2)')

        // 3D Mug: left highlight, right shadow
        c.fillStyle = '#ffffff'
        c.fillRect(5, 10, 6, 4)
        c.fillStyle = '#dddddd'
        c.fillRect(6, 11, 4, 2)
        // Left highlight
        vline(c, 5, 10, 4, '#ffffff')
        // Right shadow
        vline(c, 10, 10, 4, '#cccccc')
        // Mug handle
        px(c, 11, 11, '#eeeeee')
        px(c, 11, 12, '#dddddd')

        // Steam
        px(c, 7, 9, '#aaaaaa')
        px(c, 8, 8, '#999999')

        // Base
        c.fillStyle = '#222233'
        c.fillRect(1, 14, 14, 2)

        vline(c, 15, 0, 16, 'rgba(0,0,0,0.2)')
        hline(c, 0, 14, 16, 'rgba(0,0,0,0.25)')
        hline(c, 0, 15, 16, 'rgba(0,0,0,0.25)')
      },

      // ── 9: Door — Wood grain panels ──
      (c) => {
        const doorColor = '#5a4738'
        const panelColor = '#6a5748'
        const groove = '#4a3728'
        const brass = '#D4A844'
        c.fillStyle = doorColor
        c.fillRect(0, 0, 16, 16)

        // Frame
        c.fillStyle = '#4a3728'
        c.fillRect(0, 0, 2, 16)
        c.fillRect(14, 0, 2, 16)

        // Door surface
        c.fillStyle = doorColor
        c.fillRect(2, 0, 12, 15)

        // 3 vertical grain lines
        vline(c, 5, 1, 14, darken(doorColor, 0.06))
        vline(c, 8, 1, 14, darken(doorColor, 0.06))
        vline(c, 11, 1, 14, darken(doorColor, 0.06))

        // Top highlight
        hline(c, 2, 0, 12, lighten(doorColor, 0.15))

        // Upper panel with dithered fill
        c.fillStyle = groove
        c.fillRect(4, 2, 8, 1); c.fillRect(4, 6, 8, 1)
        vline(c, 4, 2, 5, groove); vline(c, 11, 2, 5, groove)
        dither(c, 5, 3, 6, 3, panelColor, lighten(panelColor, 0.05))

        // Lower panel with dithered fill
        c.fillStyle = groove
        c.fillRect(4, 8, 8, 1); c.fillRect(4, 12, 8, 1)
        vline(c, 4, 8, 5, groove); vline(c, 11, 8, 5, groove)
        dither(c, 5, 9, 6, 3, panelColor, lighten(panelColor, 0.05))

        // Expanded brass handle + keyhole
        px(c, 10, 7, brass)
        px(c, 10, 8, brass)
        px(c, 11, 7, lighten(brass, 0.2))
        px(c, 11, 8, darken(brass, 0.1))
        // Keyhole
        px(c, 10, 9, '#222222')

        // Threshold
        hline(c, 0, 15, 16, '#333333')

        vline(c, 15, 0, 16, 'rgba(0,0,0,0.2)')
        hline(c, 0, 14, 16, 'rgba(0,0,0,0.2)')
      },

      // ── 10: Display — LED indicator + dithered screen gradient ──
      (c) => {
        const bezel = '#111122'
        c.fillStyle = bezel
        c.fillRect(0, 0, 16, 16)

        c.fillStyle = '#1a1816'
        c.fillRect(0, 0, 16, 12)

        // Screen with dithered gradient
        dither(c, 1, 1, 14, 5, '#223355', '#1e2e4e')
        dither(c, 1, 6, 14, 5, '#1a2a44', '#162440')

        // Grid lines
        c.fillStyle = 'rgba(255,255,255,0.06)'
        for (let gy = 3; gy < 10; gy += 3) {
          c.fillRect(2, gy, 12, 1)
        }

        // Line chart (rising trend)
        const chartY = [8, 7, 8, 6, 5, 4, 5, 3, 2, 3, 2, 2]
        for (let i = 0; i < chartY.length; i++) {
          px(c, 2 + i, chartY[i], '#44ddff')
          c.fillStyle = 'rgba(68,221,255,0.1)'
          c.fillRect(2 + i, chartY[i] + 1, 1, 10 - chartY[i])
        }

        // LED indicator dot on bezel
        px(c, 14, 11, '#44ff44')

        // Bezel highlight
        hline(c, 0, 0, 16, '#2a2a3e')

        // Stand
        c.fillStyle = '#222233'
        c.fillRect(6, 12, 4, 2)
        c.fillStyle = '#333344'
        c.fillRect(4, 14, 8, 2)

        vline(c, 15, 0, 16, 'rgba(0,0,0,0.2)')
        hline(c, 0, 14, 16, 'rgba(0,0,0,0.25)')
        hline(c, 0, 15, 16, 'rgba(0,0,0,0.25)')
      },

      // ── 11: Verification Machine — Metal + LED with screw dots ──
      (c) => {
        const body = '#222244'
        const bodyLight = '#333366'
        c.fillStyle = body
        c.fillRect(0, 0, 16, 16)

        c.fillStyle = bodyLight
        c.fillRect(1, 1, 14, 14)
        hline(c, 1, 1, 14, lighten(bodyLight, 0.15))
        hline(c, 1, 14, 14, darken(body, 0.2))

        // Metallic screw dots at corners
        px(c, 2, 2, '#555577'); px(c, 13, 2, '#555577')
        px(c, 2, 13, '#555577'); px(c, 13, 13, '#555577')

        // Traffic light LEDs with dithered halo boundaries
        px(c, 3, 3, '#ff4444'); px(c, 4, 3, '#ff4444')
        dither(c, 2, 2, 4, 1, 'rgba(255,68,68,0.15)', bodyLight)
        dither(c, 2, 4, 4, 1, 'rgba(255,68,68,0.15)', bodyLight)

        px(c, 3, 6, '#ffaa00'); px(c, 4, 6, '#ffaa00')
        dither(c, 2, 5, 4, 1, 'rgba(255,170,0,0.15)', bodyLight)
        dither(c, 2, 7, 4, 1, 'rgba(255,170,0,0.15)', bodyLight)

        px(c, 3, 9, '#44ff44'); px(c, 4, 9, '#44ff44')
        dither(c, 2, 8, 4, 1, 'rgba(68,255,68,0.15)', bodyLight)
        dither(c, 2, 10, 4, 1, 'rgba(68,255,68,0.15)', bodyLight)

        // "V" badge (right side)
        c.fillStyle = '#aabbff'
        px(c, 8, 4, '#aabbff'); px(c, 12, 4, '#aabbff')
        px(c, 9, 5, '#aabbff'); px(c, 11, 5, '#aabbff')
        px(c, 9, 6, '#8899dd'); px(c, 11, 6, '#8899dd')
        px(c, 10, 7, '#8899dd')
        px(c, 10, 8, '#6677bb')

        // Scan lines
        c.fillStyle = 'rgba(100,150,255,0.2)'
        c.fillRect(7, 10, 7, 1)
        c.fillRect(7, 12, 7, 1)

        vline(c, 15, 0, 16, 'rgba(0,0,0,0.2)')
        hline(c, 0, 14, 16, 'rgba(0,0,0,0.25)')
        hline(c, 0, 15, 16, 'rgba(0,0,0,0.25)')
      },

      // ── 12: Command Desk — Multi-material ──
      (c) => {
        const desk = '#3a3a5a'
        const deskLight = '#4a4a6a'
        c.fillStyle = desk
        c.fillRect(0, 0, 16, 16)

        // L-shaped desk surface
        c.fillStyle = deskLight
        c.fillRect(0, 0, 16, 6)
        c.fillRect(0, 0, 6, 12)
        hline(c, 0, 0, 16, lighten(deskLight, 0.15))

        // Monitor 1 (blue bezel — code editor)
        c.fillStyle = '#0A0A22'
        c.fillRect(1, 1, 6, 4)
        hline(c, 1, 1, 6, '#1A1A44') // colored bezel top
        c.fillStyle = '#1a3355'
        c.fillRect(2, 2, 4, 2)
        hline(c, 2, 2, 3, '#4488cc')
        hline(c, 2, 3, 2, '#44aa88')

        // Monitor 2 (orange bezel — dashboard)
        c.fillStyle = '#221111'
        c.fillRect(9, 1, 6, 4)
        hline(c, 9, 1, 6, '#442211') // colored bezel top
        c.fillStyle = '#442211'
        c.fillRect(10, 2, 4, 2)
        hline(c, 10, 2, 3, '#ff8844')
        hline(c, 10, 3, 2, '#ffaa66')

        // Mouse pad (dithered rectangle)
        dither(c, 10, 6, 4, 3, '#333355', '#2E2E50')
        // Mouse dot
        px(c, 12, 7, '#888899')
        px(c, 13, 7, '#777788')

        // Desk shadow at edges
        hline(c, 0, 5, 16, darken(desk, 0.15))
        vline(c, 5, 6, 6, darken(desk, 0.15))

        vline(c, 15, 0, 16, 'rgba(0,0,0,0.2)')
        hline(c, 0, 14, 16, 'rgba(0,0,0,0.25)')
        hline(c, 0, 15, 16, 'rgba(0,0,0,0.25)')
      },

      // ── 13: Papers — Paper fiber texture ──
      (c) => {
        const bg = '#44403a'
        c.fillStyle = bg
        c.fillRect(0, 0, 16, 16)

        // Sheet 3 (bottom)
        c.fillStyle = '#cccccc'
        c.fillRect(7, 1, 7, 9)
        // Paper fiber: every 3rd pixel darkened
        for (let py = 1; py < 10; py++) {
          for (let ppx = 7; ppx < 14; ppx++) {
            if ((ppx + py) % 3 === 0) px(c, ppx, py, darken('#cccccc', 0.03))
          }
        }

        // Sheet 2 (middle)
        c.fillStyle = '#dddddd'
        c.fillRect(4, 3, 7, 9)
        for (let py = 3; py < 12; py++) {
          for (let ppx = 4; ppx < 11; ppx++) {
            if ((ppx + py) % 3 === 0) px(c, ppx, py, darken('#dddddd', 0.03))
          }
        }
        hline(c, 5, 5, 5, '#888888')
        hline(c, 5, 7, 4, '#888888')
        hline(c, 5, 9, 5, '#888888')

        // Sheet 1 (top)
        c.fillStyle = '#eeeeee'
        c.fillRect(1, 5, 7, 9)
        for (let py = 5; py < 14; py++) {
          for (let ppx = 1; ppx < 8; ppx++) {
            if ((ppx + py) % 3 === 0) px(c, ppx, py, darken('#eeeeee', 0.03))
          }
        }
        hline(c, 2, 7, 5, '#777777')
        hline(c, 2, 9, 4, '#777777')
        hline(c, 2, 11, 5, '#777777')

        // Paper clip with specular dot
        px(c, 12, 2, '#aabbcc')
        px(c, 13, 2, '#aabbcc')
        px(c, 13, 3, '#8899aa')
        px(c, 12, 3, '#8899aa')
        px(c, 12, 4, '#aabbcc')
        px(c, 13, 2, '#ffffff') // specular

        // Corner fold
        px(c, 7, 5, '#dddddd')
        px(c, 7, 6, '#cccccc')

        vline(c, 15, 0, 16, 'rgba(0,0,0,0.2)')
        hline(c, 0, 14, 16, 'rgba(0,0,0,0.25)')
        hline(c, 0, 15, 16, 'rgba(0,0,0,0.25)')
      },

      // ── 14: Zone Border — Lab floor with subtle divider stripe ──
      (c) => {
        // Same lab tile base as tile 0 but slightly darker
        const tileBase = '#383A40'
        c.fillStyle = tileBase
        c.fillRect(0, 0, 16, 16)

        // Matching speckle noise
        const speckles = ['#363840', '#3C3E46', '#3A3C44', '#40424C']
        for (let y = 0; y < 16; y++) {
          for (let x = 0; x < 16; x++) {
            const hash = (x * 7 + y * 13 + x * y) % 4
            if (hash === 0) px(c, x, y, speckles[(x + y) % speckles.length])
          }
        }

        // Grout lines
        hline(c, 0, 15, 16, '#30323A')
        vline(c, 15, 0, 16, '#30323A')
        hline(c, 0, 0, 16, '#3E4048')
        vline(c, 0, 0, 16, '#3E4048')

        // Subtle yellow safety stripe at center
        c.fillStyle = 'rgba(180,170,80,0.10)'
        c.fillRect(7, 0, 2, 16)
      },

      // ── 15: Empty — Dark lab black ──
      (c) => {
        c.fillStyle = '#08090C'
        c.fillRect(0, 0, 16, 16)
      },
    ]

    drawTile.forEach((draw, i) => {
      const offsetX = i * 16
      ctx.save()
      ctx.translate(offsetX, 0)
      draw(ctx)
      ctx.restore()
    })

    const tex = scene.textures.addCanvas('tileset', canvas)
    if (tex) {
      for (let i = 0; i < 16; i++) {
        tex.add(i, 0, i * 16, 0, 16, 16)
      }
    }
  }

  // ─── Agent Spritesheet ───────────────────────────────────────────────────

  static generateAgentSpritesheet(
    scene: Phaser.Scene,
    archetype: RoleArchetype,
    color: string,
  ): void {
    const config = ARCHETYPE_CONFIGS[archetype]
    const canvas = document.createElement('canvas')
    canvas.width = 192 // 12 * 16
    canvas.height = 16
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    const shirtColor = color
    const pantsColor = darken(color, 0.25)
    const shoeColor = darken(color, 0.5)
    const armColor = darken(color, 0.1)
    const skinTone = config.skinTone
    const skinHighlight = lighten(skinTone, 0.12)
    const skinShadow = darken(skinTone, 0.15)
    const hairColor = config.hairColor
    const hairHighlight = lighten(hairColor, 0.20)
    const hairShadow = darken(hairColor, 0.20)
    const eyeColor = config.eyeColor

    // Colored outline colors
    const headOutline = darken(hairColor, 0.50)
    const bodyOutline = darken(shirtColor, 0.50)
    const shoeOutline = darken(shoeColor, 0.30)

    // ── Accessory drawer per archetype ──
    const drawAccessory = (c: CanvasRenderingContext2D, bob: number, dir: number): void => {
      switch (archetype) {
        case 'pi': {
          const crownColor = '#F5C542'
          const crownDark = '#C9A030'
          hline(c, 5, bob, 6, crownColor)
          px(c, 5, bob - 1, crownColor)
          px(c, 8, bob - 1, crownColor)
          px(c, 10, bob - 1, crownColor)
          px(c, 7, bob, crownDark)
          break
        }
        case 'theorist': {
          if (dir === 0) {
            px(c, 5, 3 + bob, '#aabbdd')
            px(c, 7, 3 + bob, '#aabbdd')
            px(c, 6, 3 + bob, '#8899bb')
            px(c, 9, 3 + bob, '#aabbdd')
            px(c, 11, 3 + bob, '#aabbdd')
            px(c, 10, 3 + bob, '#8899bb')
          } else if (dir === 1) {
            px(c, 4, 3 + bob, '#aabbdd')
            px(c, 6, 3 + bob, '#aabbdd')
            px(c, 5, 3 + bob, '#8899bb')
          } else if (dir === 2) {
            px(c, 10, 3 + bob, '#aabbdd')
            px(c, 12, 3 + bob, '#aabbdd')
            px(c, 11, 3 + bob, '#8899bb')
          }
          break
        }
        case 'experimentalist': {
          hline(c, 5, 1 + bob, 6, '#77aacc')
          px(c, 6, 1 + bob, '#aaddff')
          px(c, 9, 1 + bob, '#aaddff')
          px(c, 4, 2 + bob, '#557799')
          px(c, 11, 2 + bob, '#557799')
          break
        }
        case 'critic': {
          const beretColor = '#cc3333'
          c.fillStyle = beretColor
          c.fillRect(4, bob - 1, 6, 2)
          px(c, 3, bob, beretColor)
          px(c, 10, bob - 1, beretColor)
          px(c, 10, bob - 2, darken(beretColor, 0.2))
          break
        }
        case 'synthesizer': {
          const hoodColor = '#7B5EA7'
          const hoodDark = darken(hoodColor, 0.2)
          px(c, 4, 1 + bob, hoodColor)
          px(c, 11, 1 + bob, hoodColor)
          px(c, 4, 2 + bob, hoodColor)
          px(c, 11, 2 + bob, hoodColor)
          hline(c, 5, bob, 6, hoodColor)
          hline(c, 5, bob - 1, 6, hoodDark)
          px(c, 7, bob - 1, hoodColor)
          px(c, 8, bob - 1, hoodColor)
          break
        }
        case 'scout': {
          const hatColor = '#8B7355'
          const hatDark = darken(hatColor, 0.2)
          hline(c, 3, 1 + bob, 10, hatColor)
          c.fillStyle = hatDark
          c.fillRect(5, bob - 1, 6, 2)
          c.fillRect(5, bob, 6, 1)
          hline(c, 3, 1 + bob, 10, lighten(hatColor, 0.15))
          break
        }
        case 'mentor': {
          const capColor = '#222233'
          hline(c, 3, bob, 10, capColor)
          hline(c, 4, bob - 1, 8, capColor)
          c.fillStyle = capColor
          c.fillRect(5, 1 + bob, 6, 1)
          px(c, 12, bob, '#F5C542')
          px(c, 13, 1 + bob, '#F5C542')
          break
        }
        case 'technician': {
          const hardHatColor = '#F0C030'
          const hardHatDark = darken(hardHatColor, 0.15)
          c.fillStyle = hardHatColor
          c.fillRect(5, bob, 6, 2)
          px(c, 4, 1 + bob, hardHatColor)
          px(c, 11, 1 + bob, hardHatColor)
          hline(c, 6, bob - 1, 4, hardHatColor)
          hline(c, 6, bob, 4, lighten(hardHatColor, 0.2))
          hline(c, 4, 1 + bob, 8, hardHatDark)
          break
        }
        case 'generalist': {
          px(c, 7, bob - 1, lighten(color, 0.4))
          px(c, 8, bob - 1, lighten(color, 0.4))
          px(c, 7, bob - 2, lighten(color, 0.3))
          break
        }
      }
    }

    // ── Body detail drawer ──
    const drawBodyDetail = (c: CanvasRenderingContext2D, bob: number): void => {
      switch (archetype) {
        case 'pi':
          px(c, 6, 5 + bob, '#ffffff')
          px(c, 7, 5 + bob, '#ffffff')
          px(c, 8, 5 + bob, '#ffffff')
          px(c, 9, 5 + bob, '#ffffff')
          break
        case 'experimentalist':
          vline(c, 4, 6 + bob, 5, '#eeeeee')
          vline(c, 11, 6 + bob, 5, '#eeeeee')
          hline(c, 4, 11 + bob, 8, '#dddddd')
          break
        case 'critic':
          c.fillStyle = darken(color, 0.15)
          c.fillRect(5, 7 + bob, 6, 2)
          break
        case 'synthesizer':
          vline(c, 3, 6 + bob, 6, darken(color, 0.1))
          vline(c, 12, 6 + bob, 6, darken(color, 0.1))
          break
        case 'scout':
          px(c, 5, 6 + bob, '#555555')
          px(c, 6, 7 + bob, '#555555')
          px(c, 7, 8 + bob, '#555555')
          break
        case 'mentor':
          c.fillStyle = '#884422'
          c.fillRect(3, 8 + bob, 2, 3)
          px(c, 3, 8 + bob, '#aa5533')
          break
        case 'technician':
          px(c, 5, 10 + bob, '#888888')
          px(c, 7, 10 + bob, '#888888')
          px(c, 9, 10 + bob, '#888888')
          px(c, 10, 10 + bob, '#888888')
          break
        default:
          break
      }
    }

    // ── Frame loop: 4 directions x 3 walk frames ──
    for (let dir = 0; dir < 4; dir++) {
      for (let frame = 0; frame < 3; frame++) {
        const frameIndex = dir * 3 + frame
        const offsetX = frameIndex * 16

        ctx.save()
        ctx.translate(offsetX, 0)

        // Body bob
        const bob = frame === 1 ? -1 : 0

        // ── Elliptical ground shadow ──
        ctx.fillStyle = 'rgba(0,0,0,0.12)'
        ctx.fillRect(5, 13, 6, 1)
        ctx.fillStyle = 'rgba(0,0,0,0.20)'
        ctx.fillRect(4, 14, 8, 1)
        ctx.fillStyle = 'rgba(0,0,0,0.10)'
        ctx.fillRect(3, 15, 10, 1)

        // ── Shirt (torso y 5-8) ──
        ctx.fillStyle = shirtColor
        ctx.fillRect(4, 5 + bob, 8, 4)
        // Collar
        px(ctx, 7, 5 + bob, '#EEEEEE')
        px(ctx, 8, 5 + bob, '#EEEEEE')
        // Fold shadow on left side
        vline(ctx, 5, 6 + bob, 3, darken(shirtColor, 0.15))
        // Buttons
        px(ctx, 8, 6 + bob, darken(shirtColor, 0.20))
        px(ctx, 8, 7 + bob, darken(shirtColor, 0.20))
        // Belt at bottom of shirt
        hline(ctx, 5, 8 + bob, 6, darken(shirtColor, 0.30))

        // ── Pants (lower body y 9-11) ──
        ctx.fillStyle = pantsColor
        ctx.fillRect(4, 9 + bob, 8, 3)
        // Center seam
        vline(ctx, 8, 9 + bob, 3, darken(pantsColor, 0.12))
        // Pocket dots
        px(ctx, 6, 9 + bob, darken(pantsColor, 0.20))
        px(ctx, 10, 9 + bob, darken(pantsColor, 0.20))

        // ── Arms at sides ──
        ctx.fillStyle = armColor
        const armYBase = 6 + bob
        ctx.fillRect(3, armYBase, 1, 4)
        ctx.fillRect(12, armYBase, 1, 4)
        if (frame === 1) {
          ctx.fillRect(3, 5 + bob, 1, 4)
          ctx.fillRect(12, 7 + bob, 1, 4)
        } else if (frame === 2) {
          ctx.fillRect(3, 7 + bob, 1, 4)
          ctx.fillRect(12, 5 + bob, 1, 4)
        }
        // Hands
        px(ctx, 3, 9 + bob, skinTone)
        px(ctx, 12, 9 + bob, skinTone)

        // ── Head — 3-shade skin ──
        ctx.fillStyle = skinTone
        ctx.fillRect(5, 1 + bob, 6, 5)
        // Forehead highlight (row 1)
        hline(ctx, 6, 1 + bob, 4, skinHighlight)
        // Side shadow (right 2 columns rows 2-4)
        px(ctx, 10, 2 + bob, skinShadow)
        px(ctx, 10, 3 + bob, skinShadow)
        px(ctx, 10, 4 + bob, skinShadow)
        px(ctx, 9, 3 + bob, skinShadow)
        px(ctx, 9, 4 + bob, skinShadow)
        // Chin shadow (bottom row)
        hline(ctx, 6, 5 + bob, 4, skinShadow)
        // Round corners
        ctx.clearRect(5, 1 + bob, 1, 1)
        ctx.clearRect(10, 1 + bob, 1, 1)
        ctx.clearRect(5, 5 + bob, 1, 1)
        ctx.clearRect(10, 5 + bob, 1, 1)

        // ── Hair — 3-shade shaped ──
        // Row 0: highlight center, base edges — shaped crown
        px(ctx, 6, 1 + bob, hairColor)
        hline(ctx, 7, 1 + bob, 2, hairHighlight)
        px(ctx, 9, 1 + bob, hairColor)
        // Row 1: shadow edges, base center — depth
        px(ctx, 5, 2 + bob, hairShadow)
        hline(ctx, 6, 2 + bob, 4, hairColor)
        px(ctx, 10, 2 + bob, hairShadow)
        // Side wraps
        px(ctx, 5, 3 + bob, hairColor)
        px(ctx, 10, 2 + bob, hairColor)
        if (dir === 3) { // facing up: full hair coverage
          hline(ctx, 5, 2 + bob, 6, hairHighlight)
          hline(ctx, 5, 3 + bob, 6, hairColor)
          hline(ctx, 5, 4 + bob, 6, hairShadow)
        }

        // ── Eyes with colored iris ──
        if (dir === 0) { // facing down
          // Eye whites
          ctx.fillStyle = '#ffffff'
          ctx.fillRect(6, 3 + bob, 2, 2)
          ctx.fillRect(9, 3 + bob, 2, 2)
          // Colored iris
          px(ctx, 7, 3 + bob, eyeColor)
          px(ctx, 10, 3 + bob, eyeColor)
          // Pupil
          px(ctx, 7, 4 + bob, '#111111')
          px(ctx, 10, 4 + bob, '#111111')
          // Eyelid line
          px(ctx, 6, 2 + bob, darken(skinTone, 0.20))
          px(ctx, 9, 2 + bob, darken(skinTone, 0.20))
          // Blush
          px(ctx, 6, 4 + bob, '#E8A0A0')
          px(ctx, 9, 4 + bob, '#E8A0A0')
          // Mouth
          px(ctx, 8, 4 + bob, skinShadow)
        } else if (dir === 1) { // facing left
          ctx.fillStyle = '#ffffff'
          ctx.fillRect(5, 3 + bob, 2, 2)
          px(ctx, 5, 3 + bob, eyeColor)
          px(ctx, 5, 4 + bob, '#111111')
        } else if (dir === 2) { // facing right
          ctx.fillStyle = '#ffffff'
          ctx.fillRect(10, 3 + bob, 2, 2)
          px(ctx, 11, 3 + bob, eyeColor)
          px(ctx, 11, 4 + bob, '#111111')
        }
        // up (dir === 3): no eyes visible

        // Draw archetype accessory
        drawAccessory(ctx, bob, dir)

        // Draw archetype body detail
        drawBodyDetail(ctx, bob)

        // ── Legs with shoes ──
        ctx.fillStyle = pantsColor
        if (frame === 0) {
          ctx.fillRect(5, 12 + bob, 3, 2)
          ctx.fillRect(9, 12 + bob, 3, 2)
          ctx.fillStyle = shoeColor
          ctx.fillRect(5, 14 + bob, 3, 1)
          ctx.fillRect(9, 14 + bob, 3, 1)
        } else if (frame === 1) {
          ctx.fillRect(3, 12 + bob, 3, 2)
          ctx.fillRect(9, 12 + bob, 3, 2)
          ctx.fillStyle = shoeColor
          ctx.fillRect(3, 14 + bob, 3, 1)
          ctx.fillRect(9, 14 + bob, 3, 1)
        } else {
          ctx.fillRect(5, 12 + bob, 3, 2)
          ctx.fillRect(11, 12 + bob, 3, 2)
          ctx.fillStyle = shoeColor
          ctx.fillRect(5, 14 + bob, 3, 1)
          ctx.fillRect(11, 14 + bob, 3, 1)
        }

        // ── Colored outlines ──
        // Head/hair outline
        hline(ctx, 6, bob, 4, headOutline)
        // Body/arm outline
        vline(ctx, 2, armYBase, 4, bodyOutline)
        vline(ctx, 13, armYBase, 4, bodyOutline)
        // Shoe outline
        if (frame === 0) {
          hline(ctx, 5, 15 + bob, 3, shoeOutline)
          hline(ctx, 9, 15 + bob, 3, shoeOutline)
        } else if (frame === 1) {
          hline(ctx, 3, 15 + bob, 3, shoeOutline)
          hline(ctx, 9, 15 + bob, 3, shoeOutline)
        } else {
          hline(ctx, 5, 15 + bob, 3, shoeOutline)
          hline(ctx, 11, 15 + bob, 3, shoeOutline)
        }

        ctx.restore()
      }
    }

    const tex = scene.textures.addCanvas(config.key, canvas)
    if (tex) {
      tex.add(0, 0, 0, 0, 16, 16)
      for (let i = 1; i < 12; i++) {
        tex.add(i, 0, i * 16, 0, 16, 16)
      }
    }
  }

  static generateAllAgentSpritesheets(scene: Phaser.Scene): void {
    for (const [archetype, config] of Object.entries(ARCHETYPE_CONFIGS)) {
      PlaceholderArtGenerator.generateAgentSpritesheet(
        scene,
        archetype as RoleArchetype,
        config.color,
      )
    }
  }

  static generateUITextures(scene: Phaser.Scene): void {
    // Speech bubble background
    const bubbleCanvas = document.createElement('canvas')
    bubbleCanvas.width = 32
    bubbleCanvas.height = 32
    const bCtx = bubbleCanvas.getContext('2d')
    if (!bCtx) return

    bCtx.fillStyle = '#ffffff'
    bCtx.beginPath()
    bCtx.moveTo(4, 0)
    bCtx.lineTo(28, 0)
    bCtx.quadraticCurveTo(32, 0, 32, 4)
    bCtx.lineTo(32, 22)
    bCtx.quadraticCurveTo(32, 26, 28, 26)
    bCtx.lineTo(12, 26)
    bCtx.lineTo(8, 32)
    bCtx.lineTo(8, 26)
    bCtx.lineTo(4, 26)
    bCtx.quadraticCurveTo(0, 26, 0, 22)
    bCtx.lineTo(0, 4)
    bCtx.quadraticCurveTo(0, 0, 4, 0)
    bCtx.fill()

    bCtx.strokeStyle = '#cccccc'
    bCtx.lineWidth = 1
    bCtx.stroke()

    scene.textures.addCanvas('speech-bubble', bubbleCanvas)

    // Status icons (8x8 each, 4 icons in a strip)
    const statusCanvas = document.createElement('canvas')
    statusCanvas.width = 32
    statusCanvas.height = 8
    const sCtx = statusCanvas.getContext('2d')
    if (!sCtx) return

    sCtx.fillStyle = '#44ff88'
    sCtx.beginPath()
    sCtx.arc(4, 4, 3, 0, Math.PI * 2)
    sCtx.fill()

    sCtx.fillStyle = '#ffcc44'
    sCtx.beginPath()
    sCtx.arc(12, 4, 3, 0, Math.PI * 2)
    sCtx.fill()

    sCtx.fillStyle = '#888888'
    sCtx.beginPath()
    sCtx.arc(20, 4, 3, 0, Math.PI * 2)
    sCtx.fill()

    sCtx.fillStyle = '#ff4444'
    sCtx.beginPath()
    sCtx.arc(28, 4, 3, 0, Math.PI * 2)
    sCtx.fill()

    const statusTex = scene.textures.addCanvas('status-icons', statusCanvas)
    if (statusTex) {
      for (let i = 0; i < 4; i++) {
        statusTex.add(i, 0, i * 8, 0, 8, 8)
      }
    }
  }
}
