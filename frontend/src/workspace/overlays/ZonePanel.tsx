/**
 * ZonePanel -- React overlay showing zone detail panel with agent list and research items.
 * Depends on: GameBridge, zone/archetype configs, workspace types
 */
import { useEffect, useState } from 'react'
import { GameBridge } from '../game/GameBridge'
import { getZoneById } from '../game/config/zones'
import { ARCHETYPE_CONFIGS, type RoleArchetype } from '../game/config/archetypes'
import type { WorkspaceAgent, LabMember, ResearchItem } from '@/types/workspace'
import { X, Users, FlaskConical, MessageSquare } from 'lucide-react'
import { Button } from '@/components/common/Button'

interface ZonePanelProps {
  agents: WorkspaceAgent[]
  members: LabMember[] | undefined
  research: ResearchItem[] | undefined
  onOpenRoundtable?: (researchItemId: string) => void
}

export function ZonePanel({ agents, members, research, onOpenRoundtable }: ZonePanelProps) {
  const [selectedZone, setSelectedZone] = useState<string | null>(null)

  useEffect(() => {
    const bridge = GameBridge.getInstance()

    const onZoneClick = (zoneId: string) => {
      setSelectedZone(prev => prev === zoneId ? null : zoneId)
    }

    bridge.on('zone_clicked', onZoneClick)
    return () => {
      bridge.off('zone_clicked', onZoneClick)
    }
  }, [])

  if (!selectedZone) return null

  const zoneConfig = getZoneById(selectedZone)
  if (!zoneConfig) return null

  const zoneAgents = agents.filter(a => a.zone === zoneConfig.backendZone)
  const memberLookup = new Map(members?.map(m => [m.agentId, m]) ?? [])

  const isRoundtable = selectedZone === 'roundtable'
  const debatedItems = research?.filter(r => r.status === 'under_debate') ?? []

  return (
    <div className="absolute right-0 top-0 h-full w-80 bg-card/95 backdrop-blur border-l shadow-xl z-40 overflow-y-auto">
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b">
        <div className="flex items-center gap-2">
          <div
            className="w-3 h-3 rounded-full"
            style={{ backgroundColor: zoneConfig.color }}
          />
          <h3 className="font-semibold">{zoneConfig.label}</h3>
        </div>
        <Button
          variant="ghost"
          size="icon"
          onClick={() => setSelectedZone(null)}
        >
          <X className="h-4 w-4" />
        </Button>
      </div>

      {/* Agents in zone */}
      <div className="p-4 border-b">
        <div className="flex items-center gap-2 mb-3">
          <Users className="h-4 w-4 text-muted-foreground" />
          <span className="text-sm font-medium">
            Agents ({zoneAgents.length})
          </span>
        </div>
        <div className="space-y-2">
          {zoneAgents.map(agent => {
            const member = memberLookup.get(agent.agent_id)
            const config = member
              ? ARCHETYPE_CONFIGS[member.archetype as RoleArchetype]
              : null
            return (
              <div
                key={agent.agent_id}
                className="flex items-center gap-2 p-2 rounded-md bg-muted/50"
              >
                <div
                  className="w-2 h-2 rounded-full"
                  style={{ backgroundColor: config?.color ?? '#888' }}
                />
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium truncate">
                    {member?.displayName ?? agent.agent_id.slice(0, 8)}
                  </p>
                  <p className="text-xs text-muted-foreground">
                    {config?.label ?? 'Agent'} · {agent.status}
                  </p>
                </div>
              </div>
            )
          })}
          {zoneAgents.length === 0 && (
            <p className="text-sm text-muted-foreground italic">No agents in this zone</p>
          )}
        </div>
      </div>

      {/* Zone-specific content */}
      {isRoundtable && debatedItems.length > 0 && (
        <div className="p-4">
          <div className="flex items-center gap-2 mb-3">
            <MessageSquare className="h-4 w-4 text-muted-foreground" />
            <span className="text-sm font-medium">Active Debates</span>
          </div>
          <div className="space-y-2">
            {debatedItems.map(item => (
              <button
                key={item.id}
                onClick={() => onOpenRoundtable?.(item.id)}
                className="w-full text-left p-3 rounded-md bg-red-500/10 border border-red-500/20 hover:bg-red-500/20 transition-colors"
              >
                <p className="text-sm font-medium">{item.title}</p>
                <p className="text-xs text-muted-foreground mt-1">
                  Score: {item.score.toFixed(2)} · {item.citationCount} citations
                </p>
              </button>
            ))}
          </div>
        </div>
      )}

      {selectedZone === 'bench' && (
        <div className="p-4">
          <div className="flex items-center gap-2 mb-3">
            <FlaskConical className="h-4 w-4 text-muted-foreground" />
            <span className="text-sm font-medium">Active Experiments</span>
          </div>
          {(research?.filter(r => r.status === 'in_progress') ?? []).map(item => (
            <div key={item.id} className="p-3 rounded-md bg-amber-500/10 border border-amber-500/20 mb-2">
              <p className="text-sm font-medium">{item.title}</p>
              <p className="text-xs text-muted-foreground mt-1">
                Score: {item.score.toFixed(2)}
              </p>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
