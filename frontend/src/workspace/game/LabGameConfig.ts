import Phaser from 'phaser'
import { BootScene } from './scenes/BootScene'
import { LabScene } from './scenes/LabScene'
import { CANVAS_WIDTH, CANVAS_HEIGHT } from './config/zones'

export function createLabGameConfig(parentElement: HTMLElement): Phaser.Types.Core.GameConfig {
  return {
    type: Phaser.AUTO,
    parent: parentElement,
    width: CANVAS_WIDTH,
    height: CANVAS_HEIGHT,
    pixelArt: true,
    roundPixels: true,
    backgroundColor: '#16181e',
    scale: {
      mode: Phaser.Scale.FIT,
      autoCenter: Phaser.Scale.CENTER_BOTH,
    },
    physics: {
      default: 'arcade',
      arcade: {
        gravity: { x: 0, y: 0 },
        debug: false,
      },
    },
    scene: [BootScene, LabScene],
  }
}
