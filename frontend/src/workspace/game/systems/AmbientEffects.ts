/**
 * AmbientEffects -- Zone-based ambient visual effects using Phaser tweens and particles.
 * Terminal flicker, coffee steam, data streams, page float, confetti bursts.
 * Depends on: Phaser, ZONE_CONFIGS, TILE_SIZE, SCALE
 */
import Phaser from 'phaser'
import { ZONE_CONFIGS, TILE_SIZE, SCALE, CANVAS_WIDTH, CANVAS_HEIGHT } from '../config/zones'
import { TILE_LAYER } from '../art/TilemapData'

interface AmbientHandle {
  destroy(): void
}

export class AmbientEffects {
  private scene: Phaser.Scene
  private handles: AmbientHandle[] = []

  constructor(scene: Phaser.Scene) {
    this.scene = scene
    this.initEffects()
  }

  private initEffects(): void {
    this.addTerminalFlicker()
    this.addLibraryPageFloat()
    this.addBenchDataStreams()
    this.addVerificationPulse()
    this.addLightSpots()
    this.addDustMotes()
    this.addCoffeeSteamAmbient()
    this.addTypingSparkles()
    this.addWindowLightBeam()
  }

  /**
   * Terminal/whiteboard area: subtle screen flicker effect on small rectangles.
   */
  private addTerminalFlicker(): void {
    const whiteboard = ZONE_CONFIGS.find(z => z.id === 'whiteboard')
    if (!whiteboard) return

    const rect = whiteboard.tileRect
    // Place 3 small "screen" rectangles in the whiteboard zone
    const screenPositions = [
      { x: rect.x + 1, y: rect.y + 1 },
      { x: rect.x + 3, y: rect.y + 1 },
      { x: rect.x + 2, y: rect.y + 3 },
    ]

    for (const pos of screenPositions) {
      const px = (pos.x * TILE_SIZE + TILE_SIZE / 2) * SCALE
      const py = (pos.y * TILE_SIZE + TILE_SIZE / 2) * SCALE

      const screen = this.scene.add.rectangle(px, py, 8 * SCALE, 6 * SCALE, 0x00FF88, 0.15)
      screen.setDepth(1)

      const tween = this.scene.tweens.add({
        targets: screen,
        alpha: { from: 0.08, to: 0.2 },
        duration: 800 + Math.random() * 400,
        ease: 'Sine.easeInOut',
        yoyo: true,
        repeat: -1,
        delay: Math.random() * 500,
      })

      this.handles.push({
        destroy() {
          tween.destroy()
          screen.destroy()
        },
      })
    }
  }

  /**
   * Library zone: white particles floating upward (pages).
   */
  private addLibraryPageFloat(): void {
    const library = ZONE_CONFIGS.find(z => z.id === 'library')
    if (!library) return

    const rect = library.tileRect
    const cx = (rect.x + rect.w / 2) * TILE_SIZE * SCALE
    const cy = (rect.y + rect.h - 1) * TILE_SIZE * SCALE

    // Create a simple particle that floats up
    const emitter = this.scene.add.particles(cx, cy, '__WHITE', {
      speed: { min: 5, max: 15 },
      angle: { min: 260, max: 280 },
      scale: { start: 0.3, end: 0 },
      alpha: { start: 0.3, end: 0 },
      lifespan: 3000,
      frequency: 2000,
      quantity: 1,
      tint: 0xFFFFFF,
    })
    emitter.addEmitZone({
      type: 'random',
      source: new Phaser.Geom.Rectangle(-rect.w * TILE_SIZE * SCALE / 4, 0, rect.w * TILE_SIZE * SCALE / 2, 2),
    } as Phaser.Types.GameObjects.Particles.EmitZoneData)
    emitter.setDepth(2)

    this.handles.push({
      destroy() {
        emitter.destroy()
      },
    })
  }

  /**
   * Lab bench zone: green data stream particles flowing downward.
   */
  private addBenchDataStreams(): void {
    const bench = ZONE_CONFIGS.find(z => z.id === 'bench')
    if (!bench) return

    const rect = bench.tileRect
    const cx = (rect.x + rect.w / 2) * TILE_SIZE * SCALE
    const cy = (rect.y + 1) * TILE_SIZE * SCALE

    const emitter = this.scene.add.particles(cx, cy, '__WHITE', {
      speed: { min: 10, max: 25 },
      angle: { min: 80, max: 100 },
      scale: { start: 0.2, end: 0 },
      alpha: { start: 0.4, end: 0 },
      lifespan: 2000,
      frequency: 1500,
      quantity: 1,
      tint: 0x00FF66,
    })
    emitter.addEmitZone({
      type: 'random',
      source: new Phaser.Geom.Rectangle(-rect.w * TILE_SIZE * SCALE / 3, 0, rect.w * TILE_SIZE * SCALE / 3, 2),
    } as Phaser.Types.GameObjects.Particles.EmitZoneData)
    emitter.setDepth(2)

    this.handles.push({
      destroy() {
        emitter.destroy()
      },
    })
  }

  /**
   * Verification/roundtable zone: three colored circles pulsing like a traffic light.
   */
  private addVerificationPulse(): void {
    const roundtable = ZONE_CONFIGS.find(z => z.id === 'roundtable')
    if (!roundtable) return

    const rect = roundtable.tileRect
    const baseX = (rect.x + rect.w - 1) * TILE_SIZE * SCALE
    const baseY = (rect.y + 1) * TILE_SIZE * SCALE

    const colors = [0xFF4444, 0xFFAA00, 0x44FF44]
    const lights: Phaser.GameObjects.Arc[] = []

    for (let i = 0; i < 3; i++) {
      const light = this.scene.add.circle(
        baseX,
        baseY + i * 6 * SCALE,
        2 * SCALE,
        colors[i],
        0.3,
      )
      light.setDepth(2)
      lights.push(light)

      // Staggered pulse — only one light is bright at a time
      const tween = this.scene.tweens.add({
        targets: light,
        alpha: { from: 0.15, to: 0.6 },
        duration: 1200,
        ease: 'Sine.easeInOut',
        yoyo: true,
        repeat: -1,
        delay: i * 1200,
      })

      this.handles.push({
        destroy() {
          tween.destroy()
          light.destroy()
        },
      })
    }
  }

  /**
   * Static soft glow circles near light-emitting tiles (terminals, displays, coffee machine).
   */
  private addLightSpots(): void {
    const glowMap: Record<number, { color: number; alpha: number }> = {
      4:  { color: 0x00FF88, alpha: 0.06 }, // terminal → green glow
      10: { color: 0x4488FF, alpha: 0.06 }, // display → blue glow
      8:  { color: 0xFF8844, alpha: 0.06 }, // coffee machine → warm orange glow
    }
    const radius = 2 * TILE_SIZE * SCALE

    for (let y = 0; y < TILE_LAYER.length; y++) {
      for (let x = 0; x < TILE_LAYER[y].length; x++) {
        const tileId = TILE_LAYER[y][x]
        const glow = glowMap[tileId]
        if (!glow) continue

        const px = (x * TILE_SIZE + TILE_SIZE / 2) * SCALE
        const py = (y * TILE_SIZE + TILE_SIZE / 2) * SCALE

        const circle = this.scene.add.circle(px, py, radius, glow.color, glow.alpha)
        circle.setDepth(0.8)

        this.handles.push({
          destroy() {
            circle.destroy()
          },
        })
      }
    }
  }

  /**
   * SDV-style warm dust motes floating across the scene.
   */
  private addDustMotes(): void {
    const emitter = this.scene.add.particles(CANVAS_WIDTH / 2, CANVAS_HEIGHT / 2, '__WHITE', {
      speed: { min: 1, max: 4 },
      angle: { min: 200, max: 340 },
      scale: { start: 0.18, end: 0 },
      alpha: { start: 0.20, end: 0 },
      lifespan: 12000,
      frequency: 1500,
      quantity: 1,
      tint: 0xDDDDEE,
    })
    emitter.addEmitZone({
      type: 'random',
      source: new Phaser.Geom.Rectangle(-CANVAS_WIDTH / 2, -CANVAS_HEIGHT / 2, CANVAS_WIDTH, CANVAS_HEIGHT),
    } as Phaser.Types.GameObjects.Particles.EmitZoneData)
    emitter.setDepth(3)

    this.handles.push({
      destroy() {
        emitter.destroy()
      },
    })
  }

  /**
   * Persistent small rising steam particles near coffee machine tiles.
   */
  private addCoffeeSteamAmbient(): void {
    for (let y = 0; y < TILE_LAYER.length; y++) {
      for (let x = 0; x < TILE_LAYER[y].length; x++) {
        if (TILE_LAYER[y][x] !== 8) continue // 8 = coffee machine

        const px = (x * TILE_SIZE + TILE_SIZE / 2) * SCALE
        const py = (y * TILE_SIZE) * SCALE

        const emitter = this.scene.add.particles(px, py, '__WHITE', {
          speed: { min: 3, max: 8 },
          angle: { min: 260, max: 280 },
          scale: { start: 0.2, end: 0 },
          alpha: { start: 0.18, end: 0 },
          lifespan: 2500,
          frequency: 800,
          quantity: 1,
          tint: 0xCCCCCC,
        })
        emitter.setDepth(3)

        this.handles.push({
          destroy() {
            emitter.destroy()
          },
        })
      }
    }
  }

  /**
   * Tiny fast green dots occasionally appearing near terminal tiles.
   */
  private addTypingSparkles(): void {
    for (let y = 0; y < TILE_LAYER.length; y++) {
      for (let x = 0; x < TILE_LAYER[y].length; x++) {
        if (TILE_LAYER[y][x] !== 4) continue // 4 = terminal

        const px = (x * TILE_SIZE + TILE_SIZE / 2) * SCALE
        const py = (y * TILE_SIZE + TILE_SIZE / 2) * SCALE

        const emitter = this.scene.add.particles(px, py, '__WHITE', {
          speed: { min: 10, max: 30 },
          angle: { min: 0, max: 360 },
          scale: { start: 0.12, end: 0 },
          alpha: { start: 0.5, end: 0 },
          lifespan: 500,
          frequency: 4000,
          quantity: 1,
          tint: 0x00FF88,
        })
        emitter.setDepth(3)

        this.handles.push({
          destroy() {
            emitter.destroy()
          },
        })
      }
    }
  }

  /**
   * Diagonal cool light beam from upper-right, as if fluorescent overhead light.
   */
  private addWindowLightBeam(): void {
    const gfx = this.scene.add.graphics()
    gfx.setDepth(0.6)

    // Diagonal cool trapezoid from upper-right corner
    gfx.fillStyle(0xCCDDFF, 0.025)
    gfx.beginPath()
    gfx.moveTo(CANVAS_WIDTH - 2 * TILE_SIZE * SCALE, 0)
    gfx.lineTo(CANVAS_WIDTH, 0)
    gfx.lineTo(CANVAS_WIDTH - 4 * TILE_SIZE * SCALE, 6 * TILE_SIZE * SCALE)
    gfx.lineTo(CANVAS_WIDTH - 6 * TILE_SIZE * SCALE, 4 * TILE_SIZE * SCALE)
    gfx.closePath()
    gfx.fillPath()

    this.handles.push({
      destroy() {
        gfx.destroy()
      },
    })
  }

  /**
   * Trigger a confetti burst at a world position (for celebrations).
   */
  showConfetti(worldX: number, worldY: number): void {
    const colors = [0xFF6347, 0xFFD700, 0x32CD32, 0x4169E1, 0x9370DB]

    for (const color of colors) {
      const particles = this.scene.add.particles(worldX, worldY, '__WHITE', {
        speed: { min: 30, max: 80 },
        angle: { min: 0, max: 360 },
        scale: { start: 0.4, end: 0 },
        lifespan: 1000,
        quantity: 3,
        tint: color,
        emitting: false,
      })
      particles.setDepth(100)
      particles.explode(3)

      this.scene.time.delayedCall(1200, () => {
        particles.destroy()
      })
    }
  }

  /**
   * Show coffee steam at a world position.
   */
  showSteam(worldX: number, worldY: number): void {
    const emitter = this.scene.add.particles(worldX, worldY, '__WHITE', {
      speed: { min: 3, max: 8 },
      angle: { min: 260, max: 280 },
      scale: { start: 0.3, end: 0 },
      alpha: { start: 0.25, end: 0 },
      lifespan: 2000,
      frequency: 300,
      quantity: 1,
      tint: 0xCCCCCC,
    })
    emitter.setDepth(3)

    // Auto-stop after 5 seconds
    this.scene.time.delayedCall(5000, () => {
      emitter.destroy()
    })
  }

  destroy(): void {
    for (const handle of this.handles) {
      handle.destroy()
    }
    this.handles = []
  }
}
