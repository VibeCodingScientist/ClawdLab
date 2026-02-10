/**
 * ZoneArea -- Phaser interactive zone overlay with highlight animation and click handling.
 * Depends on: Phaser, ZoneConfig
 */
import Phaser from 'phaser'
import type { ZoneConfig } from '../config/zones'
import { TILE_SIZE, SCALE } from '../config/zones'

export class ZoneArea extends Phaser.GameObjects.Container {
  private rect: Phaser.GameObjects.Rectangle
  private label: Phaser.GameObjects.Text
  private zoneConfig: ZoneConfig
  private highlightTween: Phaser.Tweens.Tween | null = null
  private activityLevel = 0

  constructor(scene: Phaser.Scene, config: ZoneConfig) {
    const pixelX = config.tileRect.x * TILE_SIZE * SCALE
    const pixelY = config.tileRect.y * TILE_SIZE * SCALE
    const pixelW = config.tileRect.w * TILE_SIZE * SCALE
    const pixelH = config.tileRect.h * TILE_SIZE * SCALE

    super(scene, pixelX + pixelW / 2, pixelY + pixelH / 2)

    this.zoneConfig = config

    // Zone overlay rectangle
    const color = Phaser.Display.Color.HexStringToColor(config.color)
    this.rect = scene.add.rectangle(0, 0, pixelW, pixelH, color.color, 0.08)
    this.rect.setStrokeStyle(1, color.color, 0.3)

    // Zone label — larger font, top-left positioning, letter-spacing
    this.label = scene.add.text(
      -pixelW / 2 + 6,
      -pixelH / 2 + 4,
      config.label.toUpperCase(),
      {
        fontFamily: 'monospace',
        fontSize: '10px',
        color: config.color,
        backgroundColor: 'rgba(0,0,0,0.55)',
        padding: { x: 4, y: 2 },
      },
    ).setOrigin(0, 0)
    this.label.setLetterSpacing(2)

    this.add([this.rect, this.label])

    // Make interactive
    this.rect.setInteractive({ useHandCursor: true })
    this.rect.on('pointerdown', () => {
      scene.events.emit('zone_clicked', config.id)
    })

    scene.add.existing(this)
    this.setDepth(1)
  }

  setHighlight(active: boolean): void {
    if (this.highlightTween) {
      this.highlightTween.stop()
      this.highlightTween = null
    }

    if (active) {
      this.highlightTween = this.scene.tweens.add({
        targets: this.rect,
        fillAlpha: { from: 0.08, to: 0.2 },
        duration: 600,
        yoyo: true,
        repeat: -1,
      })
    } else {
      this.rect.setFillStyle(
        Phaser.Display.Color.HexStringToColor(this.zoneConfig.color).color,
        0.08,
      )
    }
  }

  setActivityLevel(level: number): void {
    if (level === this.activityLevel) return
    this.activityLevel = level

    // Stop any existing highlight tween
    if (this.highlightTween) {
      this.highlightTween.stop()
      this.highlightTween = null
    }

    const color = Phaser.Display.Color.HexStringToColor(this.zoneConfig.color).color

    if (level === 0) {
      // Static baseline
      this.rect.setFillStyle(color, 0.08)
    } else {
      // Activity pulse: higher level = faster + brighter
      const maxAlpha = level === 1 ? 0.12 : level === 2 ? 0.16 : 0.20
      const duration = level === 1 ? 1000 : level === 2 ? 800 : 600

      this.highlightTween = this.scene.tweens.add({
        targets: this.rect,
        fillAlpha: { from: 0.08, to: maxAlpha },
        duration,
        yoyo: true,
        repeat: -1,
        ease: 'Sine.easeInOut',
      })
    }
  }

  getRandomSpawnPoint(): { x: number; y: number } {
    const points = this.zoneConfig.spawnPoints
    const point = points[Math.floor(Math.random() * points.length)]
    return {
      x: point.x * TILE_SIZE * SCALE,
      y: point.y * TILE_SIZE * SCALE,
    }
  }

  getConfig(): ZoneConfig {
    return this.zoneConfig
  }
}
