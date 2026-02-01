/**
 * AgentSprite -- Phaser container for an agent: sprite, name label, status text, speech bubble, pathfinding movement, and progression visuals.
 * Supports both procedural placeholder sprites and real Aseprite-exported spritesheets.
 * Depends on: Phaser, ARCHETYPE_CONFIGS, SpeechBubble, GameBridge, VisualEffects
 */
import Phaser from 'phaser'
import { ARCHETYPE_CONFIGS, type RoleArchetype } from '../config/archetypes'
import { SpeechBubble } from './SpeechBubble'
import { GameBridge } from '../GameBridge'
import { TILE_SIZE, SCALE } from '../config/zones'
import { addIdleBob } from '../systems/VisualEffects'
import type { AgentTier, AgentResearchState } from '@/types/workspace'

const USE_REAL_ASSETS = import.meta.env.VITE_USE_REAL_ASSETS === 'true'

interface PathPoint {
  x: number
  y: number
}

const WALK_SPEED = 80 // pixels per second

export class AgentSprite extends Phaser.GameObjects.Container {
  private sprite: Phaser.GameObjects.Sprite
  private nameLabel: Phaser.GameObjects.Text
  private shadow: Phaser.GameObjects.Ellipse
  private statusText: Phaser.GameObjects.Text
  private currentBubble: SpeechBubble | null = null
  private _idleBobTween: Phaser.Tweens.Tween | null = null

  private path: PathPoint[] = []
  private pathIndex = 0
  private isWalking = false
  private currentDirection = 'down'

  readonly agentId: string
  readonly archetype: RoleArchetype
  readonly displayName: string

  globalLevel = 0
  tier: AgentTier = 'novice'
  prestigeCount = 0
  researchState: AgentResearchState = 'idle'

  constructor(
    scene: Phaser.Scene,
    x: number,
    y: number,
    agentId: string,
    displayName: string,
    archetype: RoleArchetype,
  ) {
    super(scene, x, y)

    this.agentId = agentId
    this.archetype = archetype
    this.displayName = displayName

    const config = ARCHETYPE_CONFIGS[archetype]

    // Shadow — larger and more opaque for better grounding
    this.shadow = scene.add.ellipse(0, 6 * SCALE, 12 * SCALE, 5 * SCALE, 0x000000, 0.35)

    // Sprite
    this.sprite = scene.add.sprite(0, 0, config.key, 0)
    this.sprite.setScale(SCALE)

    // Name label — slightly more padding and letter-spacing
    this.nameLabel = scene.add.text(0, -14 * SCALE, displayName, {
      fontFamily: 'monospace',
      fontSize: '9px',
      color: config.color,
      backgroundColor: 'rgba(0,0,0,0.6)',
      padding: { x: 4, y: 2 },
    }).setOrigin(0.5, 1)
    this.nameLabel.setLetterSpacing(1)

    // Status text
    this.statusText = scene.add.text(0, 10 * SCALE, '', {
      fontFamily: 'monospace',
      fontSize: '7px',
      color: '#aaaaaa',
      backgroundColor: 'rgba(0,0,0,0.4)',
      padding: { x: 2, y: 0 },
    }).setOrigin(0.5, 0)

    this.add([this.shadow, this.sprite, this.nameLabel, this.statusText])

    // Interactive
    this.setSize(16 * SCALE, 16 * SCALE)
    this.setInteractive({ useHandCursor: true })

    this.on('pointerover', () => {
      const worldPos = this.getWorldTransformMatrix()
      const camera = scene.cameras.main
      const screenX = (worldPos.tx - camera.scrollX) * camera.zoom
      const screenY = (worldPos.ty - camera.scrollY) * camera.zoom
      GameBridge.getInstance().emit('agent_hovered', this.agentId, screenX, screenY)
    })

    this.on('pointerout', () => {
      GameBridge.getInstance().emit('agent_unhovered')
    })

    this.on('pointerdown', () => {
      GameBridge.getInstance().emit('agent_clicked', this.agentId)
    })

    scene.add.existing(this)
    this.setDepth(10)

    // Start idle bob animation
    this._idleBobTween = addIdleBob(scene, this)
  }

  /** Expose the inner sprite for effects (glow, tint). */
  getSprite(): Phaser.GameObjects.Sprite {
    return this.sprite
  }

  /** Get the archetype base color as a hex number. */
  getBaseColor(): number {
    const config = ARCHETYPE_CONFIGS[this.archetype]
    return parseInt(config.color.replace('#', ''), 16)
  }

  /**
   * Build the animation key for this archetype.
   * When using real Aseprite assets, the JSON atlas may embed frame tags
   * with a different naming convention. This helper normalises it.
   */
  private animKey(action: 'walk' | 'idle', direction: string): string {
    if (USE_REAL_ASSETS) {
      // Aseprite frame tags: "theorist-walk-down", same format but may
      // also support "theorist_walk_down" — normalise to dash.
      return `${this.archetype}-${action}-${direction}`
    }
    return `${this.archetype}-${action}-${direction}`
  }

  walkTo(path: PathPoint[]): void {
    if (path.length === 0) return

    this.path = path.map(p => ({
      x: p.x * TILE_SIZE * SCALE,
      y: p.y * TILE_SIZE * SCALE,
    }))
    this.pathIndex = 0
    this.isWalking = true
    this.updateDirection()
    this.sprite.play(this.animKey('walk', this.currentDirection))
  }

  update(_time: number, delta: number): void {
    if (!this.isWalking || this.path.length === 0) return

    const target = this.path[this.pathIndex]
    const dx = target.x - this.x
    const dy = target.y - this.y
    const dist = Math.sqrt(dx * dx + dy * dy)

    const step = (WALK_SPEED * delta) / 1000

    if (dist <= step) {
      this.setPosition(target.x, target.y)
      this.pathIndex++

      if (this.pathIndex >= this.path.length) {
        this.isWalking = false
        this.sprite.play(this.animKey('idle', this.currentDirection))
        return
      }

      this.updateDirection()
      this.sprite.play(this.animKey('walk', this.currentDirection))
    } else {
      const moveX = (dx / dist) * step
      const moveY = (dy / dist) * step
      this.setPosition(this.x + moveX, this.y + moveY)
    }
  }

  private updateDirection(): void {
    if (this.pathIndex >= this.path.length) return
    const target = this.path[this.pathIndex]
    const dx = target.x - this.x
    const dy = target.y - this.y

    if (Math.abs(dx) > Math.abs(dy)) {
      this.currentDirection = dx > 0 ? 'right' : 'left'
    } else {
      this.currentDirection = dy > 0 ? 'down' : 'up'
    }
  }

  showBubble(text: string, duration = 3000): void {
    if (this.currentBubble) {
      this.currentBubble.destroy()
      this.currentBubble = null
    }
    // Create bubble at relative offset and add as child so it follows the agent
    const bubble = new SpeechBubble(
      this.scene,
      0,
      -20 * SCALE,
      text,
      duration,
    )
    this.add(bubble)
    this.currentBubble = bubble
  }

  setStatus(status: string): void {
    this.statusText.setText(status)
  }

  destroy(fromScene?: boolean): void {
    if (this._idleBobTween) {
      this._idleBobTween.destroy()
      this._idleBobTween = null
    }
    if (this.currentBubble) {
      this.currentBubble.destroy()
      this.currentBubble = null
    }
    super.destroy(fromScene)
  }
}
