/**
 * AgentManager -- Manages agent sprites: creation, pathfinding movement, removal, and status updates.
 * Depends on: Phaser, AgentSprite, PathfindingSystem, zone configs
 */
import Phaser from 'phaser'
import { AgentSprite } from '../entities/AgentSprite'
import { PathfindingSystem } from './PathfindingSystem'
import type { WorkspaceAgentExtended, WorkspaceZone } from '@/types/workspace'
import { getZoneByBackendZone, TILE_SIZE, SCALE, ZONE_CONFIGS } from '../config/zones'
import type { ZoneConfig } from '../config/zones'

export class AgentManager {
  private scene: Phaser.Scene
  private agents: Map<string, AgentSprite> = new Map()
  private pathfinding: PathfindingSystem
  /** Maps agentId → { zoneId, slotIndex } */
  private slotAssignments: Map<string, { zoneId: string; slotIndex: number }> = new Map()
  /** Maps zoneId → boolean[] of occupied slots */
  private zoneSlotOccupancy: Map<string, boolean[]> = new Map()

  constructor(scene: Phaser.Scene) {
    this.scene = scene
    this.pathfinding = new PathfindingSystem()

    // Initialize slot occupancy for all zones
    for (const config of ZONE_CONFIGS) {
      this.zoneSlotOccupancy.set(config.id, new Array(config.spawnPoints.length).fill(false))
    }
  }

  private releaseSlot(agentId: string): void {
    const assignment = this.slotAssignments.get(agentId)
    if (!assignment) return

    const occupancy = this.zoneSlotOccupancy.get(assignment.zoneId)
    if (occupancy && assignment.slotIndex >= 0 && assignment.slotIndex < occupancy.length) {
      occupancy[assignment.slotIndex] = false
    }
    this.slotAssignments.delete(agentId)
  }

  private assignSlot(agentId: string, zoneConfig: ZoneConfig): { x: number; y: number } {
    const occupancy = this.zoneSlotOccupancy.get(zoneConfig.id)
    if (!occupancy) return { x: zoneConfig.centerTile.x, y: zoneConfig.centerTile.y }

    const freeIndex = occupancy.indexOf(false)
    if (freeIndex !== -1) {
      occupancy[freeIndex] = true
      this.slotAssignments.set(agentId, { zoneId: zoneConfig.id, slotIndex: freeIndex })
      return zoneConfig.spawnPoints[freeIndex]
    }

    // Overflow — no dedicated slot
    this.slotAssignments.set(agentId, { zoneId: zoneConfig.id, slotIndex: -1 })
    return {
      x: zoneConfig.centerTile.x + (Math.random() - 0.5) * 2,
      y: zoneConfig.centerTile.y + (Math.random() - 0.5) * 2,
    }
  }

  addAgent(extended: WorkspaceAgentExtended): AgentSprite {
    // Remove existing if present
    if (this.agents.has(extended.agent_id)) {
      this.removeAgent(extended.agent_id)
    }

    const zone = getZoneByBackendZone(extended.zone)
    if (zone.spawnPoints.length === 0) return this.addAgentAtCenter(extended, zone)

    const spawn = this.assignSlot(extended.agent_id, zone)

    const sprite = new AgentSprite(
      this.scene,
      spawn.x * TILE_SIZE * SCALE,
      spawn.y * TILE_SIZE * SCALE,
      extended.agent_id,
      extended.displayName,
      extended.archetype,
    )

    sprite.setStatus(extended.status)
    this.agents.set(extended.agent_id, sprite)
    return sprite
  }

  async moveAgent(agentId: string, zone: WorkspaceZone, _x: number, _y: number): Promise<void> {
    const sprite = this.agents.get(agentId)
    if (!sprite) return

    // Release old slot
    this.releaseSlot(agentId)

    const zoneConfig = getZoneByBackendZone(zone)
    if (zoneConfig.spawnPoints.length === 0) return

    const target = this.assignSlot(agentId, zoneConfig)

    const currentTileX = Math.round(sprite.x / (TILE_SIZE * SCALE))
    const currentTileY = Math.round(sprite.y / (TILE_SIZE * SCALE))

    const path = await this.pathfinding.findPath(
      currentTileX,
      currentTileY,
      Math.round(target.x),
      Math.round(target.y),
    )

    sprite.walkTo(path)
  }

  removeAgent(agentId: string): void {
    this.releaseSlot(agentId)
    const sprite = this.agents.get(agentId)
    if (sprite) {
      sprite.destroy()
      this.agents.delete(agentId)
    }
  }

  showBubble(agentId: string, text: string, duration = 3000): void {
    const sprite = this.agents.get(agentId)
    if (sprite) {
      sprite.showBubble(text, duration)
    }
  }

  updateStatus(agentId: string, status: string): void {
    const sprite = this.agents.get(agentId)
    if (sprite) {
      sprite.setStatus(status)
    }
  }

  getAgent(agentId: string): AgentSprite | undefined {
    return this.agents.get(agentId)
  }

  private addAgentAtCenter(extended: WorkspaceAgentExtended, zone: import('../config/zones').ZoneConfig): AgentSprite {
    const sprite = new AgentSprite(
      this.scene,
      zone.centerTile.x * TILE_SIZE * SCALE,
      zone.centerTile.y * TILE_SIZE * SCALE,
      extended.agent_id,
      extended.displayName,
      extended.archetype,
    )
    sprite.setStatus(extended.status)
    this.agents.set(extended.agent_id, sprite)
    return sprite
  }

  getAllAgents(): Map<string, AgentSprite> {
    return this.agents
  }

  update(time: number, delta: number): void {
    for (const sprite of this.agents.values()) {
      sprite.update(time, delta)
    }
  }

  destroy(): void {
    for (const sprite of this.agents.values()) {
      sprite.destroy()
    }
    this.agents.clear()
  }
}
