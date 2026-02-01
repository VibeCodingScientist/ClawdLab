/**
 * SpeechBubble -- Phaser speech bubble container with word-wrap and auto-destroy timer.
 * Depends on: Phaser
 */
import Phaser from 'phaser'

const MAX_WIDTH = 120
const PADDING = 6
const ARROW_HEIGHT = 6
const BG_COLOR = 0xffffff
const BORDER_COLOR = 0xcccccc
const TEXT_COLOR = '#333333'

export class SpeechBubble extends Phaser.GameObjects.Container {
  private bg: Phaser.GameObjects.Graphics
  private label: Phaser.GameObjects.Text

  constructor(scene: Phaser.Scene, x: number, y: number, text: string, duration = 3000) {
    super(scene, x, y)

    this.label = scene.add.text(0, 0, text, {
      fontFamily: 'monospace',
      fontSize: '8px',
      color: TEXT_COLOR,
      wordWrap: { width: MAX_WIDTH - PADDING * 2 },
      align: 'left',
    }).setOrigin(0.5, 1)

    const textBounds = this.label.getBounds()
    const bubbleWidth = Math.min(MAX_WIDTH, textBounds.width + PADDING * 2)
    const bubbleHeight = textBounds.height + PADDING * 2

    this.bg = scene.add.graphics()
    this.bg.fillStyle(BG_COLOR, 0.95)
    this.bg.lineStyle(1, BORDER_COLOR, 1)

    // Bubble body
    this.bg.fillRoundedRect(
      -bubbleWidth / 2,
      -bubbleHeight - ARROW_HEIGHT,
      bubbleWidth,
      bubbleHeight,
      4,
    )
    this.bg.strokeRoundedRect(
      -bubbleWidth / 2,
      -bubbleHeight - ARROW_HEIGHT,
      bubbleWidth,
      bubbleHeight,
      4,
    )

    // Arrow
    this.bg.fillTriangle(
      -4, -ARROW_HEIGHT,
      4, -ARROW_HEIGHT,
      0, 0,
    )

    this.label.setPosition(0, -ARROW_HEIGHT - PADDING)

    this.add([this.bg, this.label])
    // Note: Do NOT call scene.add.existing(this) here.
    // The bubble is added as a child of AgentSprite's container.

    // Auto-destroy (guard against parent being destroyed first)
    scene.time.delayedCall(duration, () => {
      if (this.active) this.destroy()
    })

    // Fade in
    this.setAlpha(0)
    scene.tweens.add({
      targets: this,
      alpha: 1,
      duration: 200,
    })
  }
}
