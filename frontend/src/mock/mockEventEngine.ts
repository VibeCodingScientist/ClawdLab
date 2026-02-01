/**
 * MockEventEngine -- Simulates workspace events with weighted zone transitions and speech bubbles.
 * Depends on: workspace types, MOCK_EXTENDED_AGENTS, SPEECH_TEXTS
 */
import type { WorkspaceEvent, WorkspaceZone, WorkspaceAgentExtended, RoleArchetype } from '@/types/workspace'
import { MOCK_EXTENDED_AGENTS, SPEECH_TEXTS } from './mockData'

type EventCallback = (event: WorkspaceEvent) => void
type BubbleCallback = (agentId: string, text: string) => void

const ZONES: WorkspaceZone[] = ['ideation', 'library', 'bench', 'roundtable', 'whiteboard', 'presentation']

// Weighted zone preferences by archetype
const ZONE_WEIGHTS: Record<RoleArchetype, Record<WorkspaceZone, number>> = {
  pi:              { ideation: 40, library: 10, bench: 5, roundtable: 25, whiteboard: 10, presentation: 10 },
  theorist:        { ideation: 15, library: 25, bench: 5, roundtable: 15, whiteboard: 30, presentation: 10 },
  experimentalist: { ideation: 5, library: 5, bench: 50, roundtable: 15, whiteboard: 5, presentation: 20 },
  critic:          { ideation: 10, library: 15, bench: 5, roundtable: 40, whiteboard: 15, presentation: 15 },
  synthesizer:     { ideation: 10, library: 10, bench: 10, roundtable: 20, whiteboard: 20, presentation: 30 },
  scout:           { ideation: 10, library: 45, bench: 5, roundtable: 10, whiteboard: 10, presentation: 20 },
  mentor:          { ideation: 25, library: 15, bench: 10, roundtable: 25, whiteboard: 15, presentation: 10 },
  technician:      { ideation: 5, library: 5, bench: 50, roundtable: 10, whiteboard: 10, presentation: 20 },
  generalist:      { ideation: 15, library: 15, bench: 15, roundtable: 20, whiteboard: 15, presentation: 20 },
}

function weightedRandomZone(archetype: RoleArchetype): WorkspaceZone {
  const weights = ZONE_WEIGHTS[archetype]
  const total = Object.values(weights).reduce((a, b) => a + b, 0)
  let r = Math.random() * total
  for (const zone of ZONES) {
    r -= weights[zone]
    if (r <= 0) return zone
  }
  return ZONES[0]
}

function randomBetween(min: number, max: number): number {
  return Math.floor(Math.random() * (max - min + 1)) + min
}

const STATUS_BY_ZONE: Record<WorkspaceZone, string[]> = {
  ideation: ['brainstorming', 'directing', 'planning'],
  library: ['reviewing', 'scanning', 'reading'],
  bench: ['experimenting', 'calibrating', 'running simulation'],
  roundtable: ['debating', 'voting', 'presenting argument'],
  whiteboard: ['theorizing', 'diagramming', 'deriving'],
  presentation: ['synthesizing', 'presenting', 'reporting'],
}

export class MockEventEngine {
  private moveInterval: ReturnType<typeof setInterval> | null = null
  private bubbleInterval: ReturnType<typeof setInterval> | null = null
  private speed = 1
  private slug: string
  private onEvent: EventCallback
  private onBubble: BubbleCallback
  private agents: WorkspaceAgentExtended[]
  private baseMoveMs = 5000
  private baseBubbleMs = 12000

  constructor(slug: string, onEvent: EventCallback, onBubble: BubbleCallback) {
    this.slug = slug
    this.onEvent = onEvent
    this.onBubble = onBubble
    // Deep-clone to avoid mutating shared mock data on re-mounts
    this.agents = (MOCK_EXTENDED_AGENTS[slug] ?? []).map(a => ({ ...a }))
  }

  start(baseMoveMs = 5000, baseBubbleMs = 12000): void {
    this.baseMoveMs = baseMoveMs
    this.baseBubbleMs = baseBubbleMs

    // Emit initial events for all agents so they appear immediately
    for (const agent of this.agents) {
      const event: WorkspaceEvent = {
        lab_id: this.slug,
        agent_id: agent.agent_id,
        zone: agent.zone,
        position_x: agent.position_x,
        position_y: agent.position_y,
        status: agent.status,
        action: 'initial_state',
        timestamp: new Date().toISOString(),
      }
      this.onEvent(event)
    }

    this.scheduleMove(baseMoveMs)
    this.scheduleBubble(baseBubbleMs)
  }

  stop(): void {
    if (this.moveInterval) clearInterval(this.moveInterval)
    if (this.bubbleInterval) clearInterval(this.bubbleInterval)
    this.moveInterval = null
    this.bubbleInterval = null
  }

  setSpeed(multiplier: number): void {
    this.speed = multiplier
    // Restart intervals with new speed using stored base values
    this.stop()
    if (multiplier > 0) {
      this.scheduleMove(this.baseMoveMs)
      this.scheduleBubble(this.baseBubbleMs)
    }
  }

  private scheduleMove(baseMs: number): void {
    const interval = baseMs / this.speed
    this.moveInterval = setInterval(() => {
      if (this.agents.length === 0) return

      const agent = this.agents[randomBetween(0, this.agents.length - 1)]
      const newZone = weightedRandomZone(agent.archetype)
      const statuses = STATUS_BY_ZONE[newZone]
      const status = statuses[randomBetween(0, statuses.length - 1)]

      // Update agent in mock data
      agent.zone = newZone
      agent.status = status

      const event: WorkspaceEvent = {
        lab_id: this.slug,
        agent_id: agent.agent_id,
        zone: newZone,
        position_x: randomBetween(0, 19),
        position_y: randomBetween(0, 14),
        status,
        action: `moved_to_${newZone}`,
        timestamp: new Date().toISOString(),
      }

      this.onEvent(event)
    }, interval + randomBetween(-1000, 1000) / this.speed)
  }

  private scheduleBubble(baseMs: number): void {
    const interval = baseMs / this.speed
    this.bubbleInterval = setInterval(() => {
      if (this.agents.length === 0) return

      const agent = this.agents[randomBetween(0, this.agents.length - 1)]
      const status = agent.status || 'idle'
      const texts = SPEECH_TEXTS[status] || SPEECH_TEXTS['idle']
      const text = texts[randomBetween(0, texts.length - 1)]

      this.onBubble(agent.agent_id, text)
    }, interval + randomBetween(-2000, 2000) / this.speed)
  }
}
