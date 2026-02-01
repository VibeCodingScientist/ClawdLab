/**
 * PerformanceMonitor -- Tracks FPS and automatically disables expensive visual effects
 * when performance drops below a configurable threshold.
 * Depends on: Phaser
 */

import Phaser from 'phaser'

/** Configuration options for the PerformanceMonitor. */
export interface PerformanceMonitorOptions {
  /** FPS threshold below which performance is considered low. Default: 30 */
  fpsThreshold?: number
  /** Number of FPS samples to keep in the rolling buffer. Default: 60 */
  sampleSize?: number
  /** How often (in ms) to check the average FPS against the threshold. Default: 2000 */
  checkIntervalMs?: number
}

/** Snapshot of current performance statistics. */
export interface PerformanceStats {
  /** Rolling average FPS. */
  averageFps: number
  /** Minimum FPS in the current sample buffer. */
  minFps: number
  /** Maximum FPS in the current sample buffer. */
  maxFps: number
  /** Whether performance is currently below threshold. */
  isLow: boolean
  /** Whether expensive visual effects have been disabled. */
  effectsDisabled: boolean
}

export class PerformanceMonitor {
  /** FPS threshold below which performance is considered low. */
  private fpsThreshold: number

  /** Maximum number of samples in the circular buffer. */
  private sampleSize: number

  /** How often (ms) to evaluate the FPS average. */
  private checkIntervalMs: number

  /** Circular buffer of FPS samples. */
  private samples: number[]

  /** Current write index into the circular buffer. */
  private sampleIndex: number

  /** How many samples have been recorded so far (up to sampleSize). */
  private sampleCount: number

  /** Timestamp of the last threshold check. */
  private lastCheckTime: number

  /** Counter for consecutive checks where FPS was below threshold. */
  private consecutiveLowChecks: number

  /** Counter for consecutive checks where FPS was above threshold. */
  private consecutiveHighChecks: number

  /**
   * Whether expensive visual effects are currently disabled.
   * Set to `true` when FPS drops below threshold for 2 consecutive checks.
   * Set to `false` when FPS is above threshold for 3 consecutive checks (hysteresis).
   */
  public effectsDisabled: boolean

  /**
   * Optional callback invoked when effects are toggled on or off.
   * Receives `true` when effects are disabled, `false` when re-enabled.
   */
  public onEffectsToggled: ((disabled: boolean) => void) | null

  /**
   * Creates a new PerformanceMonitor.
   *
   * @param scene - The Phaser scene to monitor
   * @param options - Optional configuration overrides
   */
  constructor(_scene: Phaser.Scene, options?: PerformanceMonitorOptions) {
    this.fpsThreshold = options?.fpsThreshold ?? 30
    this.sampleSize = options?.sampleSize ?? 60
    this.checkIntervalMs = options?.checkIntervalMs ?? 2000

    this.samples = new Array<number>(this.sampleSize).fill(0)
    this.sampleIndex = 0
    this.sampleCount = 0
    this.lastCheckTime = 0
    this.consecutiveLowChecks = 0
    this.consecutiveHighChecks = 0
    this.effectsDisabled = false
    this.onEffectsToggled = null
  }

  /**
   * Called each frame to record FPS and periodically evaluate performance.
   *
   * @param time - The current game time in milliseconds
   * @param delta - The time elapsed since the last frame in milliseconds
   */
  update(time: number, delta: number): void {
    // Record current FPS into circular buffer
    const fps = delta > 0 ? 1000 / delta : 0
    this.samples[this.sampleIndex] = fps
    this.sampleIndex = (this.sampleIndex + 1) % this.sampleSize
    if (this.sampleCount < this.sampleSize) {
      this.sampleCount++
    }

    // Periodically check the average
    if (this.lastCheckTime === 0) {
      this.lastCheckTime = time
      return
    }

    if (time - this.lastCheckTime >= this.checkIntervalMs) {
      this.lastCheckTime = time
      this.evaluatePerformance()
    }
  }

  /**
   * Returns whether the rolling average FPS is below the configured threshold.
   *
   * @returns `true` if average FPS is below threshold
   */
  isPerformanceLow(): boolean {
    return this.getAverageFps() < this.fpsThreshold
  }

  /**
   * Computes the rolling average FPS from the sample buffer.
   *
   * @returns The average FPS, or 0 if no samples have been recorded
   */
  getAverageFps(): number {
    if (this.sampleCount === 0) return 0

    let sum = 0
    for (let i = 0; i < this.sampleCount; i++) {
      sum += this.samples[i]
    }
    return sum / this.sampleCount
  }

  /**
   * Returns a snapshot of current performance statistics.
   *
   * @returns An object containing averageFps, minFps, maxFps, isLow, and effectsDisabled
   */
  getStats(): PerformanceStats {
    if (this.sampleCount === 0) {
      return {
        averageFps: 0,
        minFps: 0,
        maxFps: 0,
        isLow: false,
        effectsDisabled: this.effectsDisabled,
      }
    }

    let min = Infinity
    let max = -Infinity
    let sum = 0

    for (let i = 0; i < this.sampleCount; i++) {
      const val = this.samples[i]
      sum += val
      if (val < min) min = val
      if (val > max) max = val
    }

    const averageFps = sum / this.sampleCount

    return {
      averageFps,
      minFps: min,
      maxFps: max,
      isLow: averageFps < this.fpsThreshold,
      effectsDisabled: this.effectsDisabled,
    }
  }

  /**
   * Cleans up the monitor. Should be called when the scene is shut down.
   */
  destroy(): void {
    this.samples = []
    this.sampleCount = 0
    this.sampleIndex = 0
    this.onEffectsToggled = null
  }

  /**
   * Internal: evaluates performance and toggles effects with hysteresis.
   * Effects are disabled after 2 consecutive low checks.
   * Effects are re-enabled after 3 consecutive high checks.
   */
  private evaluatePerformance(): void {
    const avg = this.getAverageFps()
    const isLow = avg < this.fpsThreshold

    if (isLow) {
      this.consecutiveLowChecks++
      this.consecutiveHighChecks = 0
    } else {
      this.consecutiveHighChecks++
      this.consecutiveLowChecks = 0
    }

    // Disable effects after 2 consecutive low checks
    if (!this.effectsDisabled && this.consecutiveLowChecks >= 2) {
      this.effectsDisabled = true
      console.warn(
        `[PerformanceMonitor] Effects disabled (avg FPS: ${avg.toFixed(1)}, threshold: ${this.fpsThreshold})`
      )
      if (this.onEffectsToggled) {
        this.onEffectsToggled(true)
      }
    }

    // Re-enable effects after 3 consecutive high checks (hysteresis)
    if (this.effectsDisabled && this.consecutiveHighChecks >= 3) {
      this.effectsDisabled = false
      console.warn(
        `[PerformanceMonitor] Effects re-enabled (avg FPS: ${avg.toFixed(1)}, threshold: ${this.fpsThreshold})`
      )
      if (this.onEffectsToggled) {
        this.onEffectsToggled(false)
      }
    }
  }
}
