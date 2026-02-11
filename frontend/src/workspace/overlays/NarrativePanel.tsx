/**
 * NarrativePanel -- Translates raw workspace events into human-readable prose.
 * Uses 3-tier narrative template resolution: zone:status:archetype → zone:status → zone.
 * Includes agent popovers, clickable task links, and task-change narratives.
 * Depends on: WorkspaceEvent, LabMember, NARRATIVE_TEMPLATES, TASK_CHANGE_TEMPLATES, @radix-ui/react-popover
 */
import { useMemo, useRef, useEffect, Fragment } from 'react'
import * as Popover from '@radix-ui/react-popover'
import { BookOpen } from 'lucide-react'
import type { WorkspaceEvent, LabMember } from '@/types/workspace'
import { NARRATIVE_TEMPLATES, TASK_CHANGE_TEMPLATES, MOCK_LAB_STATE, MOCK_EXTENDED_AGENTS } from '@/mock/mockData'

const ARCHETYPE_COLORS: Record<string, string> = {
  pi: 'text-amber-400',
  theorist: 'text-blue-400',
  experimentalist: 'text-green-400',
  critic: 'text-red-400',
  synthesizer: 'text-purple-400',
  scout: 'text-cyan-400',
  mentor: 'text-amber-300',
  technician: 'text-gray-400',
  generalist: 'text-slate-400',
}

const ARCHETYPE_BG: Record<string, string> = {
  pi: 'bg-amber-400',
  theorist: 'bg-blue-400',
  experimentalist: 'bg-green-400',
  critic: 'bg-red-400',
  synthesizer: 'bg-purple-400',
  scout: 'bg-cyan-400',
  mentor: 'bg-amber-300',
  technician: 'bg-gray-400',
  generalist: 'bg-slate-400',
}

interface NarrativePanelProps {
  events: WorkspaceEvent[]
  members?: LabMember[]
  slug?: string
  onHighlightItem?: (itemId: string) => void
}

interface NarrativeEntry {
  id: string
  agentId: string
  text: string
  taskItemId: string | null
  timestamp: string
}

function resolveTask(agentId: string, labSlug: string | undefined): { title: string; itemId: string } | null {
  if (!labSlug) return null
  const extAgents = MOCK_EXTENDED_AGENTS[labSlug]
  const agent = extAgents?.find(a => a.agent_id === agentId)
  if (!agent?.currentTaskId) return null
  const labState = MOCK_LAB_STATE[labSlug] ?? []
  const item = labState.find(i => i.id === agent.currentTaskId)
  if (!item) return null
  return { title: item.title, itemId: item.id }
}

function pickTemplate(templates: string[], agentId: string): string {
  const hash = agentId.split('').reduce((acc, ch) => acc + ch.charCodeAt(0), 0)
  return templates[hash % templates.length]
}

function generateNarrative(
  event: WorkspaceEvent,
  memberName: string,
  archetype: string | undefined,
  labSlug?: string,
): { text: string; taskItemId: string | null } {
  const task = resolveTask(event.agent_id, labSlug)
  const taskTitle = task?.title ?? ''
  const taskItemId = task?.itemId ?? null

  // Handle task_change events
  if (event.action === 'task_change' && taskTitle) {
    const template = pickTemplate(TASK_CHANGE_TEMPLATES, event.agent_id)
    return {
      text: template.replace('{name}', memberName).replace('{task}', taskTitle),
      taskItemId,
    }
  }

  // Tier 1: zone:status:archetype
  if (archetype) {
    const tier1Key = `${event.zone}:${event.status}:${archetype}`
    const tier1 = NARRATIVE_TEMPLATES[tier1Key]
    if (tier1 && tier1.length > 0) {
      const template = pickTemplate(tier1, event.agent_id)
      return {
        text: template.replace('{name}', memberName).replace('{task}', taskTitle),
        taskItemId: template.includes('{task}') ? taskItemId : null,
      }
    }
  }

  // Tier 2: zone:status
  const tier2Key = `${event.zone}:${event.status}`
  const tier2 = NARRATIVE_TEMPLATES[tier2Key]
  if (tier2 && tier2.length > 0) {
    const template = pickTemplate(tier2, event.agent_id)
    return {
      text: template.replace('{name}', memberName).replace('{task}', taskTitle),
      taskItemId: template.includes('{task}') ? taskItemId : null,
    }
  }

  // Tier 3: zone
  const tier3 = NARRATIVE_TEMPLATES[event.zone]
  if (tier3 && tier3.length > 0) {
    const template = pickTemplate(tier3, event.agent_id)
    return {
      text: template.replace('{name}', memberName).replace('{task}', taskTitle),
      taskItemId: template.includes('{task}') ? taskItemId : null,
    }
  }

  // Fallback: generic prose
  const action = event.action.replace(/_/g, ' ')
  return { text: `${memberName} is ${action} in the ${event.zone}.`, taskItemId: null }
}

/** Render text with *task* segments as clickable buttons */
function NarrativeText({
  text,
  taskItemId,
  onHighlightItem,
}: {
  text: string
  taskItemId: string | null
  onHighlightItem?: (itemId: string) => void
}) {
  // Split on *...* patterns
  const parts = text.split(/\*([^*]+)\*/)
  if (parts.length === 1) return <>{text}</>

  return (
    <>
      {parts.map((part, i) => {
        // Odd indices are inside *...*
        if (i % 2 === 1 && taskItemId && onHighlightItem) {
          return (
            <button
              key={i}
              className="font-medium text-primary hover:underline cursor-pointer"
              onClick={() => onHighlightItem(taskItemId)}
            >
              {part}
            </button>
          )
        }
        return <Fragment key={i}>{part}</Fragment>
      })}
    </>
  )
}

export function NarrativePanel({ events, members, slug, onHighlightItem }: NarrativePanelProps) {
  const scrollRef = useRef<HTMLDivElement>(null)

  const memberLookup = useMemo(
    () => new Map(members?.map(m => [m.agentId, m])),
    [members]
  )

  const narrativeEntries = useMemo(() => {
    return events.slice(-50).reverse().map((event): NarrativeEntry => {
      const member = memberLookup.get(event.agent_id)
      const name = member?.displayName ?? event.agent_id.slice(0, 10)
      const { text, taskItemId } = generateNarrative(event, name, member?.archetype, slug)
      return {
        id: `${event.agent_id}-${event.timestamp}-${Math.random()}`,
        agentId: event.agent_id,
        text,
        taskItemId,
        timestamp: new Date(event.timestamp).toLocaleTimeString(),
      }
    })
  }, [events, memberLookup, slug])

  // Auto-scroll to top
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = 0
    }
  }, [narrativeEntries.length])

  return (
    <div className="rounded-lg border bg-card">
      {/* Header */}
      <div className="flex items-center gap-2 p-3 border-b">
        <BookOpen className="h-4 w-4 text-muted-foreground" />
        <span className="text-sm font-medium">Lab Narrative</span>
        <span className="text-xs text-muted-foreground ml-auto">{narrativeEntries.length} events</span>
      </div>

      {/* Scrollable narrative */}
      <div ref={scrollRef} className="overflow-y-auto p-3 space-y-2" style={{ maxHeight: 300 }}>
        {narrativeEntries.length === 0 && (
          <p className="text-sm text-muted-foreground italic">
            The lab is quiet... agents are preparing for their next research session.
          </p>
        )}
        {narrativeEntries.map(entry => {
          const member = memberLookup.get(entry.agentId)
          const colorClass = member ? ARCHETYPE_COLORS[member.archetype] ?? 'text-slate-400' : 'text-slate-400'
          const bgClass = member ? ARCHETYPE_BG[member.archetype] ?? 'bg-slate-400' : 'bg-slate-400'

          // Split text into name prefix and remainder
          const displayName = member?.displayName ?? entry.agentId.slice(0, 10)
          const remainder = entry.text.startsWith(displayName)
            ? entry.text.slice(displayName.length)
            : ` ${entry.text}`

          return (
            <div key={entry.id} className="text-sm leading-relaxed">
              <span className="text-xs text-muted-foreground mr-2">{entry.timestamp}</span>
              <span className={`inline-block h-2 w-2 rounded-full ${bgClass} mr-1`} />
              {member ? (
                <AgentPopover member={member}>
                  <button className={`font-medium ${colorClass} hover:underline cursor-pointer`}>
                    {displayName}
                  </button>
                </AgentPopover>
              ) : (
                <span className="font-medium text-muted-foreground">{displayName}</span>
              )}
              <span className="text-muted-foreground">
                <NarrativeText
                  text={remainder}
                  taskItemId={entry.taskItemId}
                  onHighlightItem={onHighlightItem}
                />
              </span>
            </div>
          )
        })}
      </div>
    </div>
  )
}

function AgentPopover({ member, children }: { member: LabMember; children: React.ReactNode }) {
  const archetypeColor = ARCHETYPE_COLORS[member.archetype] ?? 'text-slate-400'

  return (
    <Popover.Root>
      <Popover.Trigger asChild>
        {children}
      </Popover.Trigger>
      <Popover.Portal>
        <Popover.Content
          className="z-50 w-64 rounded-lg border bg-card p-4 shadow-lg"
          sideOffset={5}
          align="start"
        >
          <div className="space-y-2">
            <div className="flex items-center gap-2">
              <span className="font-semibold">{member.displayName}</span>
              <span className={`text-xs font-medium capitalize ${archetypeColor}`}>
                {member.archetype}
              </span>
            </div>
            <div className="grid grid-cols-3 gap-2 text-xs">
              <div>
                <p className="text-muted-foreground">vRep</p>
                <p className="font-bold">{member.vRep.toFixed(1)}</p>
              </div>
              <div>
                <p className="text-muted-foreground">cRep</p>
                <p className="font-medium">{member.cRep.toLocaleString()}</p>
              </div>
              <div>
                <p className="text-muted-foreground">Claims</p>
                <p className="font-medium">{member.claimsCount}</p>
              </div>
            </div>
            <p className="text-xs text-muted-foreground">
              Joined {new Date(member.joinedAt).toLocaleDateString()}
            </p>
          </div>
          <Popover.Arrow className="fill-border" />
        </Popover.Content>
      </Popover.Portal>
    </Popover.Root>
  )
}
