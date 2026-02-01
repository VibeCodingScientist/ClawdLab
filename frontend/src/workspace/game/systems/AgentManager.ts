/**
 * AgentManager -- Manages agent sprites: creation, pathfinding movement, removal, and status updates.
 * Depends on: Phaser, AgentSprite, PathfindingSystem, zone configs
 */
import Phaser from 'phaser'
import { AgentSprite } from '../entities/AgentSprite'
import { PathfindingSystem } from './PathfindingSystem'
import type { WorkspaceAgentExtended, WorkspaceZone } from '@/types/workspace'
import { getZoneByBackendZone, TILE_SIZE, SCALE } from '../config/zones'

export class AgentManager {
  private scene: Phaser.Scene
  private agents: Map<string, AgentSprite> = new Map()
  private pathfinding: PathfindingSystem

  constructor(scene: Phaser.Scene) {
    this.scene = scene
    this.pathfinding = new PathfindingSystem()
  }

  addAgent(extended: WorkspaceAgentExtended): AgentSprite {
    // Remove existing if present
    if (this.agents.has(extended.agent_id)) {
      this.removeAgent(extended.agent_id)
    }

    const zone = getZoneByBackendZone(extended.zone)
    const spawnPoints = zone.spawnPoints
    if (spawnPoints.length === 0) return this.addAgentAtCenter(extended, zone)
    const spawn = spawnPoints[Math.floor(Math.random() * spawnPoints.length)]

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

    const zoneConfig = getZoneByBackendZone(zone)
    if (zoneConfig.spawnPoints.length === 0) return
    const target = zoneConfig.spawnPoints[Math.floor(Math.random() * zoneConfig.spawnPoints.length)]

    const currentTileX = Math.round(sprite.x / (TILE_SIZE * SCALE))
    const currentTileY = Math.round(sprite.y / (TILE_SIZE * SCALE))

    const path = await this.pathfinding.findPath(
      currentTileX,
      currentTileY,
      target.x,
      target.y,
    )

    sprite.walkTo(path)
  }

  removeAgent(agentId: string): void {
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
