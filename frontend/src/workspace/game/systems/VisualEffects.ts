/**
 * VisualEffects -- Level-based visual enhancements for agent sprites: idle bob, glow, prestige stars, level-up burst, parked state.
 * Depends on: Phaser
 */
import Phaser from 'phaser'
import { SCALE } from '../config/zones'

/** Tier thresholds for visual effects. */
export type AgentTier = 'novice' | 'contributor' | 'specialist' | 'expert' | 'master' | 'grandmaster'

/** Map tier strings to a numeric rank for comparisons. */
const TIER_RANK: Record<AgentTier, number> = {
  novice: 0,
  contributor: 1,
  specialist: 2,
  expert: 3,
  master: 4,
  grandmaster: 5,
}

/** Add a gentle idle bob tween to a container (y oscillation). */
export function addIdleBob(scene: Phaser.Scene, target: Phaser.GameObjects.Container): Phaser.Tweens.Tween {
  return scene.tweens.add({
    targets: target,
    y: target.y - 1,
    duration: 600,
    ease: 'Sine.easeInOut',
    yoyo: true,
    repeat: -1,
  })
}

/**
 * Create a glow outline behind the agent sprite.
 * Returns the glow game object so it can be destroyed later.
 */
export function addGlowEffect(
  scene: Phaser.Scene,
  container: Phaser.GameObjects.Container,
  sprite: Phaser.GameObjects.Sprite,
  tint: number,
): Phaser.GameObjects.Sprite {
  const glow = scene.add.sprite(sprite.x, sprite.y, sprite.texture.key, sprite.frame.name)
  glow.setScale(sprite.scaleX * 1.15, sprite.scaleY * 1.15)
  glow.setTint(tint)
  glow.setAlpha(0.25)
  glow.setBlendMode(Phaser.BlendModes.ADD)

  // Insert glow behind the main sprite in the container
  container.addAt(glow, 0)

  // Subtle pulse
  scene.tweens.add({
    targets: glow,
    alpha: { from: 0.15, to: 0.3 },
    duration: 1200,
    ease: 'Sine.easeInOut',
    yoyo: true,
    repeat: -1,
  })

  return glow
}

/**
 * Add prestige star indicators above the agent name label.
 * Returns the text object so it can be updated/destroyed later.
 */
export function addPrestigeStars(
  scene: Phaser.Scene,
  container: Phaser.GameObjects.Container,
  prestigeCount: number,
): Phaser.GameObjects.Text | null {
  if (prestigeCount <= 0) return null

  const starText = '*'.repeat(Math.min(prestigeCount, 5))
  const stars = scene.add.text(0, -18 * SCALE, starText, {
    fontFamily: 'monospace',
    fontSize: '7px',
    color: '#FFD700',
  }).setOrigin(0.5, 1)

  container.add(stars)
  return stars
}

/**
 * Play a level-up particle burst at the agent's position.
 */
export function showLevelUpBurst(scene: Phaser.Scene, worldX: number, worldY: number, color: number = 0xFFD700): void {
  // Use simple circle particles
  const particles = scene.add.particles(worldX, worldY, '__WHITE', {
    speed: { min: 40, max: 100 },
    scale: { start: 0.6, end: 0 },
    lifespan: 600,
    quantity: 12,
    tint: color,
    emitting: false,
  })

  particles.setDepth(100)
  particles.explode(12)

  // Auto-destroy after animation
  scene.time.delayedCall(800, () => {
    particles.destroy()
  })
}

/**
 * Render parked/sleeping state: reduce opacity and show "ZZZ" text.
 * Returns the zzz text so it can be destroyed on resume.
 */
export function renderParkedState(
  scene: Phaser.Scene,
  container: Phaser.GameObjects.Container,
): Phaser.GameObjects.Text {
  container.setAlpha(0.5)

  const zzz = scene.add.text(6 * SCALE, -12 * SCALE, 'ZZZ', {
    fontFamily: 'monospace',
    fontSize: '8px',
    color: '#8888cc',
  }).setOrigin(0, 1)

  container.add(zzz)

  // Gentle float animation on the ZZZ
  scene.tweens.add({
    targets: zzz,
    y: zzz.y - 4,
    alpha: { from: 0.8, to: 0.3 },
    duration: 1500,
    ease: 'Sine.easeInOut',
    yoyo: true,
    repeat: -1,
  })

  return zzz
}

/**
 * Clear parked state rendering.
 */
export function clearParkedState(
  container: Phaser.GameObjects.Container,
  zzzText: Phaser.GameObjects.Text | null,
): void {
  container.setAlpha(1)
  if (zzzText) {
    zzzText.destroy()
  }
}

/**
 * Apply a tint shift to brighten the sprite based on level.
 * Levels 10–19: subtle brightening. 20+: more pronounced.
 */
export function applyLevelTint(sprite: Phaser.GameObjects.Sprite, level: number, baseColor: number): void {
  if (level < 10) {
    sprite.clearTint()
    return
  }

  // Lighten the base color proportional to level (capped at level 50)
  const factor = Math.min((level - 10) / 40, 1) // 0 at level 10, 1 at level 50
  const r = Math.min(255, ((baseColor >> 16) & 0xFF) + Math.floor(factor * 60))
  const g = Math.min(255, ((baseColor >> 8) & 0xFF) + Math.floor(factor * 60))
  const b = Math.min(255, (baseColor & 0xFF) + Math.floor(factor * 60))
  const tint = (r << 16) | (g << 8) | b

  sprite.setTint(tint)
}

/** Get tier rank for comparison. */
export function getTierRank(tier: AgentTier): number {
  return TIER_RANK[tier] ?? 0
}
