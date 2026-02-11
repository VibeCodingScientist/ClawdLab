/**
 * useWorkspaceEvents -- React hook that syncs SSE agent state changes into GameBridge events.
 * Depends on: GameBridge, WorkspaceAgent, LabMember types
 */
import { useEffect, useRef } from 'react'
import type { WorkspaceAgent, WorkspaceAgentExtended, LabMember } from '@/types/workspace'
import { GameBridge } from '../game/GameBridge'
import { ZONE_CONFIGS } from '../game/config/zones'

export function useWorkspaceEvents(
  agents: WorkspaceAgent[],
  members: LabMember[] | undefined,
  sceneReady = false,
) {
  const prevAgentsRef = useRef<Map<string, WorkspaceAgent>>(new Map())
  const sceneReadyRef = useRef(false)
  const bridge = GameBridge.getInstance()

  useEffect(() => {
    if (!members || members.length === 0) return

    // When scene transitions to ready, clear prev map so all agents get re-emitted
    if (sceneReady && !sceneReadyRef.current) {
      sceneReadyRef.current = true
      prevAgentsRef.current = new Map()
    }

    const memberLookup = new Map(members.map(m => [m.agentId, m]))
    const prevMap = prevAgentsRef.current
    const currentIds = new Set(agents.map(a => a.agent_id))

    // Add new agents
    for (const agent of agents) {
      const prev = prevMap.get(agent.agent_id)
      const member = memberLookup.get(agent.agent_id)

      if (!prev) {
        // New agent — add to scene
        const extended: WorkspaceAgentExtended = {
          ...agent,
          displayName: member?.displayName ?? agent.agent_id.slice(0, 8),
          archetype: member?.archetype ?? 'generalist',
          labReputation: member?.reputation ?? 0,
          globalLevel: 0,
          tier: 'novice',
          prestigeCount: 0,
          researchState: 'idle',
        }
        bridge.emit('add_agent', extended)
      } else if (prev.zone !== agent.zone || prev.status !== agent.status) {
        // Agent moved or status changed
        bridge.emit('move_agent', agent.agent_id, agent.zone, agent.position_x, agent.position_y)
        if (prev.status !== agent.status) {
          bridge.emit('update_agent_status', agent.agent_id, agent.status)
        }
      }
    }

    // Remove departed agents
    for (const [id] of prevMap) {
      if (!currentIds.has(id)) {
        bridge.emit('remove_agent', id)
      }
    }

    // Update ref
    prevAgentsRef.current = new Map(agents.map(a => [a.agent_id, a]))

    // Compute per-zone agent counts → emit zone_activity events
    const zoneCounts: Record<string, number> = {}
    for (const agent of agents) {
      zoneCounts[agent.zone] = (zoneCounts[agent.zone] ?? 0) + 1
    }
    for (const config of ZONE_CONFIGS) {
      // Map zone IDs to backend zones for counting
      const count = zoneCounts[config.backendZone] ?? 0
      const level = count === 0 ? 0 : count <= 1 ? 1 : count <= 3 ? 2 : 3
      bridge.emit('zone_activity', config.id, level)
    }
  }, [agents, members, bridge, sceneReady])
}
