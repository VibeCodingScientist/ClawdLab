/**
 * WhiteboardRenderer -- Renders a live lab state scoreboard inside the whiteboard zone.
 * Shows top 3 lab state items with status icons and verification scores.
 * Listens for `update_lab_state` and `update_progress` bridge events.
 * Depends on: Phaser, GameBridge, zones config
 */
import Phaser from 'phaser'
import { GameBridge } from '../GameBridge'
import { getZoneById, TILE_SIZE, SCALE } from '../config/zones'

const STATUS_ICONS: Record<string, string> = {
  established: '\u2713',
  under_investigation: '\u2315',
  contested: '\u2694',
  proposed: '\u2726',
  next: '\u2192',
}

function scoreColor(score: number | null): string {
  if (score === null) return '#888888'
  if (score >= 0.85) return '#4ADE80'
  if (score >= 0.70) return '#FBBF24'
  return '#EF6461'
}

export class WhiteboardRenderer {
  private bridge = GameBridge.getInstance()
  private titleText: Phaser.GameObjects.Text
  private line1: Phaser.GameObjects.Text
  private line2: Phaser.GameObjects.Text
  private line3: Phaser.GameObjects.Text

  constructor(scene: Phaser.Scene) {

    const zone = getZoneById('whiteboard')
    if (!zone) {
      // Whiteboard zone not found — create invisible placeholders
      this.titleText = scene.add.text(0, 0, '', {}).setVisible(false)
      this.line1 = scene.add.text(0, 0, '', {}).setVisible(false)
      this.line2 = scene.add.text(0, 0, '', {}).setVisible(false)
      this.line3 = scene.add.text(0, 0, '', {}).setVisible(false)
      return
    }

    const baseX = (zone.tileRect.x + 1) * TILE_SIZE * SCALE + 4
    const baseY = (zone.tileRect.y + 2) * TILE_SIZE * SCALE

    const textStyle: Phaser.Types.GameObjects.Text.TextStyle = {
      fontFamily: 'monospace',
      fontSize: '7px',
      color: '#CCCCDD',
    }

    this.titleText = scene.add.text(baseX, baseY, 'LAB STATE', {
      ...textStyle,
      fontSize: '8px',
      color: '#FFFFFF',
    }).setDepth(5)

    this.line1 = scene.add.text(baseX, baseY + 14, '', { ...textStyle }).setDepth(5)
    this.line2 = scene.add.text(baseX, baseY + 26, '', { ...textStyle }).setDepth(5)
    this.line3 = scene.add.text(baseX, baseY + 38, '', { ...textStyle }).setDepth(5)

    // Listen for lab state updates
    this.bridge.on('update_lab_state', this.onUpdateLabState)

    // Keep backward compat with progress updates
    this.bridge.on('update_progress', this.onUpdateProgress)
  }

  private onUpdateLabState = (items: { title: string; score: number | null; status: string }[]): void => {
    const lines = [this.line1, this.line2, this.line3]
    for (let i = 0; i < 3; i++) {
      const item = items[i]
      if (item) {
        const icon = STATUS_ICONS[item.status] ?? '?'
        const truncTitle = item.title.length > 22 ? item.title.slice(0, 22) + '...' : item.title
        const scoreStr = item.score !== null ? `${(item.score * 100).toFixed(0)}%` : '---'
        lines[i].setText(`${icon} ${truncTitle}  ${scoreStr}`)
        lines[i].setColor(scoreColor(item.score))
      } else {
        lines[i].setText('')
      }
    }
  }

  private onUpdateProgress = (verified: number, inProgress: number, underDebate: number): void => {
    // Fallback if no lab state items are emitted
    this.line1.setText(`\u2713 Verified: ${verified}`).setColor('#4ADE80')
    this.line2.setText(`\u25CF In Progress: ${inProgress}`).setColor('#FBBF24')
    this.line3.setText(`\u25CF Under Debate: ${underDebate}`).setColor('#EF6461')
  }

  destroy(): void {
    this.bridge.off('update_lab_state', this.onUpdateLabState)
    this.bridge.off('update_progress', this.onUpdateProgress)
    this.titleText.destroy()
    this.line1.destroy()
    this.line2.destroy()
    this.line3.destroy()
  }
}
