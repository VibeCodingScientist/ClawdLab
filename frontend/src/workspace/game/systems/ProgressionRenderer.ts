/**
 * ProgressionRenderer -- Applies level-based visual progression to AgentSprite containers.
 * Manages glow, tint, prestige stars, parked state per agent.
 * Depends on: Phaser, VisualEffects, AgentSprite
 */
import Phaser from 'phaser'
import type { AgentTier } from './VisualEffects'
import {
  addGlowEffect,
  addPrestigeStars,
  applyLevelTint,
  renderParkedState,
  clearParkedState,
  showLevelUpBurst,
} from './VisualEffects'

interface AgentVisualState {
  level: number
  tier: AgentTier
  prestigeCount: number
  isParked: boolean
  glowSprite: Phaser.GameObjects.Sprite | null
  prestigeText: Phaser.GameObjects.Text | null
  zzzText: Phaser.GameObjects.Text | null
}

/**
 * Tracks and applies visual progression effects for all agents in the scene.
 */
export class ProgressionRenderer {
  private scene: Phaser.Scene
  private agentStates: Map<string, AgentVisualState> = new Map()

  constructor(scene: Phaser.Scene) {
    this.scene = scene
  }

  /**
   * Update an agent's visual progression state.
   * Call this when level/tier/prestige changes arrive via GameBridge.
   */
  updateAgentProgression(
    agentId: string,
    container: Phaser.GameObjects.Container,
    sprite: Phaser.GameObjects.Sprite,
    level: number,
    tier: AgentTier,
    prestigeCount: number,
    baseColor: number,
  ): void {
    const prev = this.agentStates.get(agentId)

    // Clean up previous effects if they exist
    if (prev) {
      if (prev.glowSprite) {
        prev.glowSprite.destroy()
      }
      if (prev.prestigeText) {
        prev.prestigeText.destroy()
      }
    }

    // Apply level-based tint
    applyLevelTint(sprite, level, baseColor)

    // Glow effect for level 30+
    let glowSprite: Phaser.GameObjects.Sprite | null = null
    if (level >= 30) {
      glowSprite = addGlowEffect(this.scene, container, sprite, baseColor)
    }

    // Prestige stars
    let prestigeText: Phaser.GameObjects.Text | null = null
    if (prestigeCount > 0) {
      prestigeText = addPrestigeStars(this.scene, container, prestigeCount)
    }

    // Preserve parked state if it was set
    const isParked = prev?.isParked ?? false
    const zzzText = prev?.zzzText ?? null

    this.agentStates.set(agentId, {
      level,
      tier,
      prestigeCount,
      isParked,
      glowSprite,
      prestigeText,
      zzzText,
    })
  }

  /**
   * Set agent parked (sleeping) visual state.
   */
  setParked(agentId: string, container: Phaser.GameObjects.Container, parked: boolean): void {
    const state = this.agentStates.get(agentId)

    if (parked) {
      // Clear any existing ZZZ first
      if (state?.zzzText) {
        state.zzzText.destroy()
      }
      const zzzText = renderParkedState(this.scene, container)
      if (state) {
        state.isParked = true
        state.zzzText = zzzText
      } else {
        this.agentStates.set(agentId, {
          level: 0,
          tier: 'novice',
          prestigeCount: 0,
          isParked: true,
          glowSprite: null,
          prestigeText: null,
          zzzText,
        })
      }
    } else {
      clearParkedState(container, state?.zzzText ?? null)
      if (state) {
        state.isParked = false
        state.zzzText = null
      }
    }
  }

  /**
   * Trigger a level-up celebration burst at the agent's world position.
   */
  triggerLevelUp(worldX: number, worldY: number, color?: number): void {
    showLevelUpBurst(this.scene, worldX, worldY, color)
  }

  /**
   * Remove all visual state for an agent (on removal from scene).
   */
  removeAgent(agentId: string): void {
    const state = this.agentStates.get(agentId)
    if (state) {
      state.glowSprite?.destroy()
      state.prestigeText?.destroy()
      state.zzzText?.destroy()
      this.agentStates.delete(agentId)
    }
  }

  /**
   * Get current visual state for an agent.
   */
  getState(agentId: string): AgentVisualState | undefined {
    return this.agentStates.get(agentId)
  }

  destroy(): void {
    for (const [, state] of this.agentStates) {
      state.glowSprite?.destroy()
      state.prestigeText?.destroy()
      state.zzzText?.destroy()
    }
    this.agentStates.clear()
  }
}
