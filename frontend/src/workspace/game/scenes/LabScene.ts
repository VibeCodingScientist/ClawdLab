/**
 * LabScene -- Main Phaser scene rendering the tilemap, zones, agent sprites, ambient effects, and progression visuals.
 * Supports Tiled JSON maps (via TiledMapLoader) with fallback to hardcoded TILE_LAYER.
 * Depends on: GameBridge, AgentManager, EventProcessor, AmbientEffects, ProgressionRenderer, ZONE_CONFIGS, TiledMapLoader
 */
import Phaser from 'phaser'
import { TILE_LAYER } from '../art/TilemapData'
import { ZONE_CONFIGS, TILE_SIZE, SCALE, MAP_WIDTH, MAP_HEIGHT, CANVAS_WIDTH, CANVAS_HEIGHT } from '../config/zones'
// Heavy furniture tiles that cast floor shadows
const HEAVY_TILES = new Set([2, 3, 6, 8, 11, 12])
// Lamp tiles that emit warm light
const LAMP_TILES = new Set([4, 8, 10, 12])
import { ZoneArea } from '../entities/ZoneArea'
import { AgentManager } from '../systems/AgentManager'
import { EventProcessor } from '../systems/EventProcessor'
import { AmbientEffects } from '../systems/AmbientEffects'
import { ProgressionRenderer } from '../systems/ProgressionRenderer'
import { WhiteboardRenderer } from '../systems/WhiteboardRenderer'
import { GameBridge } from '../GameBridge'
import type { AgentTier, AgentResearchState, WorkspaceAgentExtended, WorkspaceZone } from '@/types/workspace'

export class LabScene extends Phaser.Scene {
  private agentManager!: AgentManager
  private eventProcessor!: EventProcessor
  private ambientEffects!: AmbientEffects
  private progressionRenderer!: ProgressionRenderer
  private whiteboardRenderer!: WhiteboardRenderer
  private zones: Map<string, ZoneArea> = new Map()
  private bridge = GameBridge.getInstance()

  constructor() {
    super({ key: 'LabScene' })
  }

  create(): void {
    // Warm background gradient beneath tiles
    this.addBackgroundGradient()
    // Build tilemap from hardcoded data (TiledMapLoader used only when real assets exist)
    this.buildTilemap(TILE_LAYER)
    this.addFurnitureShadows()
    this.addDecorativeDetails()
    this.addWarmLightSpots()
    this.addZoneFloorTints()
    this.createZones()
    this.addZoneBoundaryLines()
    this.addVignette()

    this.agentManager = new AgentManager(this)
    this.eventProcessor = new EventProcessor(this.agentManager)
    this.ambientEffects = new AmbientEffects(this)
    this.progressionRenderer = new ProgressionRenderer(this)
    this.whiteboardRenderer = new WhiteboardRenderer(this)

    // Wire zone click events to bridge
    this.events.on('zone_clicked', (zoneId: string) => {
      this.bridge.emit('zone_clicked', zoneId)
    })

    // Handle add/move/remove agent from React (driven by useWorkspaceEvents)
    this.bridge.on('add_agent', (extended: WorkspaceAgentExtended) => {
      this.agentManager.addAgent(extended)
    })

    this.bridge.on('move_agent', (agentId: string, zone: WorkspaceZone, x: number, y: number) => {
      this.agentManager.moveAgent(agentId, zone, x, y)
    })

    this.bridge.on('remove_agent', (agentId: string) => {
      this.agentManager.removeAgent(agentId)
    })

    this.bridge.on('update_agent_status', (agentId: string, status: string) => {
      this.agentManager.updateStatus(agentId, status)
    })

    this.bridge.on('show_bubble', (agentId: string, text: string, duration: number) => {
      this.agentManager.showBubble(agentId, text, duration)
    })

    // Handle zone activity level from React
    this.bridge.on('zone_activity', (zoneId: string, level: number) => {
      const zone = this.zones.get(zoneId)
      if (zone) {
        zone.setActivityLevel(level)
      }
    })

    // Handle highlight_zone from React
    this.bridge.on('highlight_zone', (zoneId: string, active: boolean) => {
      const zone = this.zones.get(zoneId)
      if (zone) {
        zone.setHighlight(active)
      }
    })

    // Handle progression updates from React
    this.bridge.on('update_agent_level', (agentId: string, level: number, tier: AgentTier, prestigeCount: number) => {
      const agentSprite = this.agentManager.getAgent(agentId)
      if (agentSprite) {
        agentSprite.globalLevel = level
        agentSprite.tier = tier
        agentSprite.prestigeCount = prestigeCount
        this.progressionRenderer.updateAgentProgression(
          agentId,
          agentSprite,
          agentSprite.getSprite(),
          level,
          tier,
          prestigeCount,
          agentSprite.getBaseColor(),
        )
      }
    })

    this.bridge.on('update_agent_research_state', (agentId: string, researchState: AgentResearchState) => {
      const agentSprite = this.agentManager.getAgent(agentId)
      if (agentSprite) {
        agentSprite.researchState = researchState
        const isParked = researchState === 'parked'
        this.progressionRenderer.setParked(agentId, agentSprite, isParked)
      }
    })

    this.bridge.on('agent_level_up', (agentId: string, _newLevel: number, color: number) => {
      const agentSprite = this.agentManager.getAgent(agentId)
      if (agentSprite) {
        const matrix = agentSprite.getWorldTransformMatrix()
        this.progressionRenderer.triggerLevelUp(matrix.tx, matrix.ty, color)
        this.ambientEffects.showConfetti(matrix.tx, matrix.ty)
      }
    })

    // Clean up on shutdown/destroy
    this.events.on('shutdown', this.shutdown, this)
    this.events.on('destroy', this.shutdown, this)

    // Signal scene is ready
    this.bridge.emit('scene_ready')
  }

  private buildTilemap(tileGrid: number[][] = TILE_LAYER): void {
    if (!this.textures.exists('tileset')) return

    for (let y = 0; y < MAP_HEIGHT; y++) {
      for (let x = 0; x < MAP_WIDTH; x++) {
        const tileIndex = tileGrid[y]?.[x] ?? 0
        const pixelX = x * TILE_SIZE * SCALE
        const pixelY = y * TILE_SIZE * SCALE

        const tile = this.add.image(
          pixelX + (TILE_SIZE * SCALE) / 2,
          pixelY + (TILE_SIZE * SCALE) / 2,
          'tileset',
          tileIndex,
        )
        tile.setScale(SCALE)
        tile.setDepth(0)
      }
    }
  }

  /** Draw a colored tint rectangle over each zone at very low alpha for atmosphere. */
  private addZoneFloorTints(): void {
    const zoneTints: Record<string, number> = {
      'pi-desk': 0xFFD700,
      'ideation': 0xFFA500,
      'library': 0x4169E1,
      'whiteboard': 0x9370DB,
      'bench': 0x32CD32,
      'roundtable': 0xFF6347,
      'presentation': 0x00CED1,
      'entrance': 0x8B6914,
    }

    for (const config of ZONE_CONFIGS) {
      const tint = zoneTints[config.id] ?? 0x888888
      const px = config.tileRect.x * TILE_SIZE * SCALE
      const py = config.tileRect.y * TILE_SIZE * SCALE
      const pw = config.tileRect.w * TILE_SIZE * SCALE
      const ph = config.tileRect.h * TILE_SIZE * SCALE

      const rect = this.add.rectangle(
        px + pw / 2,
        py + ph / 2,
        pw,
        ph,
        tint,
        0.08,
      )
      rect.setDepth(0.5)
    }
  }

  /** Radial vignette overlay: transparent center, dark edges. */
  private addVignette(): void {
    const vignetteCanvas = document.createElement('canvas')
    vignetteCanvas.width = CANVAS_WIDTH
    vignetteCanvas.height = CANVAS_HEIGHT
    const vCtx = vignetteCanvas.getContext('2d')
    if (!vCtx) return

    const gradient = vCtx.createRadialGradient(
      CANVAS_WIDTH / 2, CANVAS_HEIGHT / 2, CANVAS_WIDTH * 0.25,
      CANVAS_WIDTH / 2, CANVAS_HEIGHT / 2, CANVAS_WIDTH * 0.65,
    )
    gradient.addColorStop(0, 'rgba(0,0,0,0)')
    gradient.addColorStop(1, 'rgba(0,0,0,0.25)')
    vCtx.fillStyle = gradient
    vCtx.fillRect(0, 0, CANVAS_WIDTH, CANVAS_HEIGHT)

    const tex = this.textures.addCanvas('vignette', vignetteCanvas)
    if (tex) {
      const img = this.add.image(CANVAS_WIDTH / 2, CANVAS_HEIGHT / 2, 'vignette')
      img.setDepth(50)
      img.setScrollFactor(0)
    }
  }

  /** Warm radial background gradient at depth -1, behind everything. */
  private addBackgroundGradient(): void {
    const bgCanvas = document.createElement('canvas')
    bgCanvas.width = CANVAS_WIDTH
    bgCanvas.height = CANVAS_HEIGHT
    const bgCtx = bgCanvas.getContext('2d')
    if (!bgCtx) return

    const gradient = bgCtx.createRadialGradient(
      CANVAS_WIDTH / 2, CANVAS_HEIGHT / 2, 0,
      CANVAS_WIDTH / 2, CANVAS_HEIGHT / 2, CANVAS_WIDTH * 0.7,
    )
    gradient.addColorStop(0, '#3C3E44')
    gradient.addColorStop(1, '#35373D')
    bgCtx.fillStyle = gradient
    bgCtx.fillRect(0, 0, CANVAS_WIDTH, CANVAS_HEIGHT)

    const tex = this.textures.addCanvas('bg-gradient', bgCanvas)
    if (tex) {
      const img = this.add.image(CANVAS_WIDTH / 2, CANVAS_HEIGHT / 2, 'bg-gradient')
      img.setDepth(-1)
      img.setScrollFactor(0)
    }
  }

  /** Furniture floor shadows: semi-transparent strips on adjacent south/east floor tiles. */
  private addFurnitureShadows(): void {
    const gfx = this.add.graphics()
    gfx.setDepth(0.2)

    for (let y = 0; y < MAP_HEIGHT; y++) {
      for (let x = 0; x < MAP_WIDTH; x++) {
        const tileId = TILE_LAYER[y]?.[x] ?? 0
        if (!HEAVY_TILES.has(tileId)) continue

        // South shadow (4px tall strip on tile below)
        if (y + 1 < MAP_HEIGHT && TILE_LAYER[y + 1]?.[x] === 0) {
          const sx = x * TILE_SIZE * SCALE
          const sy = (y + 1) * TILE_SIZE * SCALE
          gfx.fillStyle(0x000000, 0.10)
          gfx.fillRect(sx, sy, TILE_SIZE * SCALE, 4 * SCALE)
        }

        // East shadow (3px wide strip on tile to the right)
        if (x + 1 < MAP_WIDTH && TILE_LAYER[y]?.[x + 1] === 0) {
          const sx = (x + 1) * TILE_SIZE * SCALE
          const sy = y * TILE_SIZE * SCALE
          gfx.fillStyle(0x000000, 0.06)
          gfx.fillRect(sx, sy, 3 * SCALE, TILE_SIZE * SCALE)
        }
      }
    }
  }

  /** Fluorescent light spots near equipment tiles (terminals, displays, coffee machines). */
  private addWarmLightSpots(): void {
    const radius = 1.5 * TILE_SIZE * SCALE
    for (let y = 0; y < MAP_HEIGHT; y++) {
      for (let x = 0; x < MAP_WIDTH; x++) {
        const tileId = TILE_LAYER[y]?.[x] ?? 0
        if (!LAMP_TILES.has(tileId)) continue

        // Check adjacent floor tiles to place light on
        const neighbors = [
          [x, y + 1], [x, y - 1], [x - 1, y], [x + 1, y],
        ]
        for (const [nx, ny] of neighbors) {
          if (nx < 0 || ny < 0 || nx >= MAP_WIDTH || ny >= MAP_HEIGHT) continue
          if (TILE_LAYER[ny]?.[nx] !== 0) continue

          const px = (nx * TILE_SIZE + TILE_SIZE / 2) * SCALE
          const py = (ny * TILE_SIZE + TILE_SIZE / 2) * SCALE
          // Cool fluorescent white glow, not warm orange
          const circle = this.add.circle(px, py, radius, 0xCCDDFF, 0.04)
          circle.setDepth(0.6)
          break // Only one spot per lamp tile
        }
      }
    }
  }

  /** Decorative scatter details above floor (depth 0.3), below furniture. */
  private addDecorativeDetails(): void {
    const gfx = this.add.graphics()
    gfx.setDepth(0.3)

    // Cable lines connecting terminal-area tiles (1px dark grey)
    gfx.lineStyle(1, 0x333330, 0.3)
    const cableY = 5 * TILE_SIZE * SCALE
    gfx.beginPath()
    gfx.moveTo(8 * TILE_SIZE * SCALE, cableY)
    gfx.lineTo(12 * TILE_SIZE * SCALE, cableY)
    gfx.strokePath()

    // Coffee ring stains near coffee machine area (3px semi-transparent brown circles)
    gfx.fillStyle(0x4a3020, 0.12)
    const coffeeBaseX = 14 * TILE_SIZE * SCALE
    const coffeeBaseY = 3 * TILE_SIZE * SCALE
    gfx.fillCircle(coffeeBaseX + 8, coffeeBaseY + 20, 4)
    gfx.fillCircle(coffeeBaseX + 24, coffeeBaseY + 10, 3)

    // Tiny pencils near whiteboard zone (1x4px yellow)
    gfx.fillStyle(0xccaa30, 0.35)
    const wbX = 3 * TILE_SIZE * SCALE + 10
    const wbY = 8 * TILE_SIZE * SCALE + 6
    gfx.fillRect(wbX, wbY, 1, 4)
    gfx.fillRect(wbX + 12, wbY + 3, 4, 1)

    // Debris dots near entrance (green/brown 1px)
    const entranceX = 8 * TILE_SIZE * SCALE
    const entranceY = 14 * TILE_SIZE * SCALE
    gfx.fillStyle(0x556644, 0.25)
    gfx.fillRect(entranceX + 5, entranceY + 2, 1, 1)
    gfx.fillRect(entranceX + 18, entranceY + 6, 1, 1)
    gfx.fillStyle(0x665544, 0.25)
    gfx.fillRect(entranceX + 10, entranceY + 4, 1, 1)
    gfx.fillRect(entranceX + 25, entranceY + 8, 1, 1)

    // Anti-static floor mat near entrance door (tile ~1,13)
    const matX = 1 * TILE_SIZE * SCALE
    const matY = 13 * TILE_SIZE * SCALE
    gfx.fillStyle(0x2A3040, 0.30)
    gfx.fillRect(matX + 4, matY + 8, TILE_SIZE * SCALE * 2 - 8, TILE_SIZE * SCALE - 12)

    // Wall clock (digital readout style above PI desk ~2,0)
    const clockX = (2 * TILE_SIZE + TILE_SIZE / 2) * SCALE
    const clockY = (0 * TILE_SIZE + TILE_SIZE / 2) * SCALE + 6
    gfx.lineStyle(1, 0x667788, 0.4)
    gfx.strokeCircle(clockX, clockY, 4 * SCALE)
    gfx.beginPath()
    gfx.moveTo(clockX, clockY)
    gfx.lineTo(clockX, clockY - 3 * SCALE)
    gfx.strokePath()
    gfx.beginPath()
    gfx.moveTo(clockX, clockY)
    gfx.lineTo(clockX + 2 * SCALE, clockY)
    gfx.strokePath()

    // Safety hazard stripe near bench area (yellow/black)
    const stripeX = (0 * TILE_SIZE + TILE_SIZE / 2) * SCALE
    const stripeY = (4 * TILE_SIZE) * SCALE - 2
    gfx.fillStyle(0xBBAA30, 0.12)
    gfx.fillRect(stripeX, stripeY, MAP_WIDTH * TILE_SIZE * SCALE - TILE_SIZE * SCALE, 2)
  }

  private createZones(): void {
    for (const config of ZONE_CONFIGS) {
      const zone = new ZoneArea(this, config)
      this.zones.set(config.id, zone)
    }
  }

  /** Draw 1px hairlines at zone edges for subtle spatial separation. */
  private addZoneBoundaryLines(): void {
    const gfx = this.add.graphics()
    gfx.setDepth(0.7)
    gfx.lineStyle(1, 0x888888, 0.06)

    for (const config of ZONE_CONFIGS) {
      const px = config.tileRect.x * TILE_SIZE * SCALE
      const py = config.tileRect.y * TILE_SIZE * SCALE
      const pw = config.tileRect.w * TILE_SIZE * SCALE
      const ph = config.tileRect.h * TILE_SIZE * SCALE

      gfx.strokeRect(px, py, pw, ph)
    }
  }

  update(time: number, delta: number): void {
    this.agentManager.update(time, delta)
  }

  getAgentManager(): AgentManager {
    return this.agentManager
  }

  getEventProcessor(): EventProcessor {
    return this.eventProcessor
  }

  getProgressionRenderer(): ProgressionRenderer {
    return this.progressionRenderer
  }

  getAmbientEffects(): AmbientEffects {
    return this.ambientEffects
  }

  shutdown(): void {
    this.events.off('zone_clicked')
    this.bridge.off('add_agent')
    this.bridge.off('move_agent')
    this.bridge.off('remove_agent')
    this.bridge.off('update_agent_status')
    this.bridge.off('show_bubble')
    this.bridge.off('highlight_zone')
    this.bridge.off('zone_activity')
    this.bridge.off('update_progress')
    this.bridge.off('update_agent_level')
    this.bridge.off('update_agent_research_state')
    this.bridge.off('agent_level_up')
    this.whiteboardRenderer?.destroy()
    this.progressionRenderer?.destroy()
    this.ambientEffects?.destroy()
    this.eventProcessor?.destroy()
    this.agentManager?.destroy()
  }
}
