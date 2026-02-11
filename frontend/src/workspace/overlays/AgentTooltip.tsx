/**
 * AgentTooltip -- React overlay tooltip shown on agent hover with name, role, and status.
 * Depends on: GameBridge, ARCHETYPE_CONFIGS, LabMember type
 */
import { useEffect, useState } from 'react'
import { GameBridge } from '../game/GameBridge'
import type { LabMember, WorkspaceAgentExtended, RoleArchetype } from '@/types/workspace'
import { ARCHETYPE_CONFIGS } from '../game/config/archetypes'
import { MOCK_LAB_STATE, MOCK_EXTENDED_AGENTS } from '@/mock/mockData'
import { ROLE_WEIGHTS } from '@/utils/domainStyles'
import type { RoleAction } from '@/utils/domainStyles'

interface AgentTooltipProps {
  members: LabMember[] | undefined
  slug?: string
}

interface TooltipState {
  visible: boolean
  agentId: string
  screenX: number
  screenY: number
}

export function AgentTooltip({ members, slug }: AgentTooltipProps) {
  const [tooltip, setTooltip] = useState<TooltipState>({
    visible: false,
    agentId: '',
    screenX: 0,
    screenY: 0,
  })

  useEffect(() => {
    const bridge = GameBridge.getInstance()

    const onHover = (agentId: string, screenX: number, screenY: number) => {
      setTooltip({ visible: true, agentId, screenX, screenY })
    }

    const onUnhover = () => {
      setTooltip(prev => ({ ...prev, visible: false }))
    }

    bridge.on('agent_hovered', onHover)
    bridge.on('agent_unhovered', onUnhover)

    return () => {
      bridge.off('agent_hovered', onHover)
      bridge.off('agent_unhovered', onUnhover)
    }
  }, [])

  if (!tooltip.visible) return null

  const member = members?.find(m => m.agentId === tooltip.agentId)
  if (!member) return null

  const config = ARCHETYPE_CONFIGS[member.archetype as RoleArchetype]

  return (
    <div
      className="absolute z-50 pointer-events-none"
      style={{
        left: tooltip.screenX + 16,
        top: tooltip.screenY - 8,
      }}
    >
      <div className="bg-card border rounded-lg shadow-lg p-3 min-w-[180px]">
        <div className="flex items-center gap-2 mb-2">
          <div
            className="w-3 h-3 rounded-full"
            style={{ backgroundColor: config?.color ?? '#888' }}
          />
          <span className="font-semibold text-sm">{member.displayName}</span>
        </div>
        <div className="space-y-1 text-xs text-muted-foreground">
          <div className="flex justify-between">
            <span>Role</span>
            <span
              className="font-medium"
              style={{ color: config?.color ?? '#888' }}
            >
              {config?.label ?? member.archetype}
            </span>
          </div>
          <div className="flex justify-between">
            <span>vRep</span>
            <span className="font-bold text-foreground">{member.vRep.toFixed(1)}</span>
          </div>
          <div className="flex justify-between">
            <span>cRep</span>
            <span className="font-medium text-foreground">{member.cRep.toLocaleString()}</span>
          </div>
          <div className="flex justify-between">
            <span>Claims</span>
            <span className="font-medium text-foreground">{member.claimsCount}</span>
          </div>
          {(() => {
            const weights = ROLE_WEIGHTS[member.archetype]
            if (!weights) return null
            const primary = (Object.entries(weights) as [RoleAction, number][])
              .filter(([, w]) => w >= 0.8)
              .map(([action]) => action)
            if (primary.length === 0) return null
            return (
              <div className="flex justify-between">
                <span>Primary</span>
                <span className="font-medium text-foreground capitalize">{primary.join(', ')}</span>
              </div>
            )
          })()}
          {slug && (() => {
            const extAgent = MOCK_EXTENDED_AGENTS[slug]?.find((a: WorkspaceAgentExtended) => a.agent_id === member.agentId)
            if (!extAgent?.currentTaskId) return null
            const labState = MOCK_LAB_STATE[slug] ?? []
            const task = labState.find(i => i.id === extAgent.currentTaskId)
            if (!task) return null
            return (
              <div className="flex justify-between">
                <span>Working on</span>
                <span className="font-medium text-foreground truncate max-w-[120px]">{task.title}</span>
              </div>
            )
          })()}
        </div>
      </div>
    </div>
  )
}
