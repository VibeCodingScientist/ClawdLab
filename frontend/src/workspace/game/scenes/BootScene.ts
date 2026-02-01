/**
 * BootScene -- Phaser boot scene that generates placeholder textures and walking animations.
 * Supports loading real PNG assets from /assets/ when VITE_USE_REAL_ASSETS=true,
 * otherwise falls back to procedural PlaceholderArtGenerator.
 * Depends on: Phaser, PlaceholderArtGenerator, ARCHETYPE_CONFIGS
 */
import Phaser from 'phaser'
import { PlaceholderArtGenerator } from '../art/PlaceholderArtGenerator'
import { ARCHETYPE_CONFIGS } from '../config/archetypes'

const USE_REAL_ASSETS = import.meta.env.VITE_USE_REAL_ASSETS === 'true'

export class BootScene extends Phaser.Scene {
  constructor() {
    super({ key: 'BootScene' })
  }

  preload(): void {
    // Create loading bar
    const width = this.cameras.main.width
    const height = this.cameras.main.height

    const progressBar = this.add.graphics()
    const progressBox = this.add.graphics()
    progressBox.fillStyle(0x222244, 0.8)
    progressBox.fillRect(width / 2 - 160, height / 2 - 25, 320, 50)

    const loadingLabel = USE_REAL_ASSETS ? 'Loading Lab Assets...' : 'Generating Lab Assets...'
    const loadingText = this.add.text(width / 2, height / 2 - 50, loadingLabel, {
      fontFamily: 'monospace',
      fontSize: '16px',
      color: '#ffffff',
    }).setOrigin(0.5)

    const percentText = this.add.text(width / 2, height / 2, '0%', {
      fontFamily: 'monospace',
      fontSize: '14px',
      color: '#ffffff',
    }).setOrigin(0.5)

    // Progress tracking
    let progress = 0
    const totalSteps = Object.keys(ARCHETYPE_CONFIGS).length + 2 // agents + tileset + UI
    let currentStep = 0

    const stepProgress = () => {
      currentStep++
      progress = currentStep / totalSteps
      progressBar.clear()
      progressBar.fillStyle(0x4466cc, 1)
      progressBar.fillRect(width / 2 - 150, height / 2 - 15, 300 * progress, 30)
      percentText.setText(`${Math.floor(progress * 100)}%`)
    }

    // Generate 1x1 white pixel for particle effects
    const whiteTexture = this.textures.createCanvas('__WHITE', 2, 2)
    if (whiteTexture) {
      const ctx = whiteTexture.getContext()
      ctx.fillStyle = '#ffffff'
      ctx.fillRect(0, 0, 2, 2)
      whiteTexture.refresh()
    }

    if (USE_REAL_ASSETS) {
      // Load real PNG assets from /assets/ directory
      this.load.on('progress', (value: number) => {
        progressBar.clear()
        progressBar.fillStyle(0x4466cc, 1)
        progressBar.fillRect(width / 2 - 150, height / 2 - 15, 300 * value, 30)
        percentText.setText(`${Math.floor(value * 100)}%`)
      })

      // Load tileset spritesheet
      this.load.spritesheet('tileset', '/assets/tiles/tileset.png', {
        frameWidth: 16,
        frameHeight: 16,
      })

      // Load agent spritesheets (Aseprite-exported PNGs)
      for (const [_archetype, config] of Object.entries(ARCHETYPE_CONFIGS)) {
        this.load.spritesheet(config.key, `/assets/agents/${config.key}.png`, {
          frameWidth: 16,
          frameHeight: 16,
        })
      }

      // Load UI textures
      this.load.image('speech-bubble', '/assets/ui/speech-bubble.png')

      // Load overlay textures if they exist
      this.load.image('prestige-stars', '/assets/overlays/prestige-stars.png')

      console.log('[BootScene] Loading real assets from /assets/')
    } else {
      // Generate procedural placeholder art
      PlaceholderArtGenerator.generateTileset(this)
      stepProgress()

      PlaceholderArtGenerator.generateAllAgentSpritesheets(this)
      for (let i = 0; i < Object.keys(ARCHETYPE_CONFIGS).length; i++) {
        stepProgress()
      }

      PlaceholderArtGenerator.generateUITextures(this)
      stepProgress()

      console.log('[BootScene] Using procedural placeholder art')
    }

    // Cleanup loading UI after a brief delay
    this.time.delayedCall(300, () => {
      progressBar.destroy()
      progressBox.destroy()
      loadingText.destroy()
      percentText.destroy()
    })
  }

  create(): void {
    // Validate all required textures were generated
    const requiredTextures = ['tileset', ...Object.values(ARCHETYPE_CONFIGS).map(c => c.key)]
    for (const key of requiredTextures) {
      if (!this.textures.exists(key)) {
        console.error(`BootScene: Missing required texture "${key}". Aborting scene transition.`)
        return
      }
    }

    // Create walk animations for each archetype
    for (const [archetype, config] of Object.entries(ARCHETYPE_CONFIGS)) {
      const directions = ['down', 'left', 'right', 'up']
      directions.forEach((dir, dirIndex) => {
        this.anims.create({
          key: `${archetype}-walk-${dir}`,
          frames: this.anims.generateFrameNumbers(config.key, {
            start: dirIndex * 3,
            end: dirIndex * 3 + 2,
          }),
          frameRate: 6,
          repeat: -1,
        })

        this.anims.create({
          key: `${archetype}-idle-${dir}`,
          frames: [{ key: config.key, frame: dirIndex * 3 }],
          frameRate: 1,
          repeat: 0,
        })
      })
    }

    this.scene.start('LabScene')
  }
}
