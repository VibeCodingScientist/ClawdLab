/**
 * WhiteboardRenderer -- Renders a live research scoreboard inside the whiteboard zone.
 * Listens for `update_progress` bridge events and updates Phaser text objects.
 * Depends on: Phaser, GameBridge, zones config
 */
import Phaser from 'phaser'
import { GameBridge } from '../GameBridge'
import { getZoneById, TILE_SIZE, SCALE } from '../config/zones'

export class WhiteboardRenderer {
  private bridge = GameBridge.getInstance()
  private titleText: Phaser.GameObjects.Text
  private verifiedText: Phaser.GameObjects.Text
  private progressText: Phaser.GameObjects.Text
  private debateText: Phaser.GameObjects.Text

  constructor(scene: Phaser.Scene) {

    const zone = getZoneById('whiteboard')
    if (!zone) {
      // Whiteboard zone not found — create invisible placeholders
      this.titleText = scene.add.text(0, 0, '', {}).setVisible(false)
      this.verifiedText = scene.add.text(0, 0, '', {}).setVisible(false)
      this.progressText = scene.add.text(0, 0, '', {}).setVisible(false)
      this.debateText = scene.add.text(0, 0, '', {}).setVisible(false)
      return
    }

    const baseX = (zone.tileRect.x + 1) * TILE_SIZE * SCALE + 4
    const baseY = (zone.tileRect.y + 2) * TILE_SIZE * SCALE

    const textStyle: Phaser.Types.GameObjects.Text.TextStyle = {
      fontFamily: 'monospace',
      fontSize: '7px',
      color: '#CCCCDD',
    }

    this.titleText = scene.add.text(baseX, baseY, 'RESEARCH STATUS', {
      ...textStyle,
      fontSize: '8px',
      color: '#FFFFFF',
    }).setDepth(5)

    this.verifiedText = scene.add.text(baseX, baseY + 14, '● Verified: 0', {
      ...textStyle,
      color: '#4ADE80',
    }).setDepth(5)

    this.progressText = scene.add.text(baseX, baseY + 26, '● In Progress: 0', {
      ...textStyle,
      color: '#FBBF24',
    }).setDepth(5)

    this.debateText = scene.add.text(baseX, baseY + 38, '● Under Debate: 0', {
      ...textStyle,
      color: '#EF6461',
    }).setDepth(5)

    // Listen for progress updates
    this.bridge.on('update_progress', this.onUpdateProgress)
  }

  private onUpdateProgress = (verified: number, inProgress: number, underDebate: number): void => {
    this.verifiedText.setText(`● Verified: ${verified}`)
    this.progressText.setText(`● In Progress: ${inProgress}`)
    this.debateText.setText(`● Under Debate: ${underDebate}`)
  }

  destroy(): void {
    this.bridge.off('update_progress', this.onUpdateProgress)
    this.titleText.destroy()
    this.verifiedText.destroy()
    this.progressText.destroy()
    this.debateText.destroy()
  }
}
