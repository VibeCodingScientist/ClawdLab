/**
 * NarrativePanel -- Translates raw workspace events into human-readable prose.
 * Includes agent popovers showing stats when clicking an agent name.
 * Depends on: WorkspaceEvent, LabMember, NARRATIVE_TEMPLATES, @radix-ui/react-popover
 */
import { useMemo, useRef, useEffect } from 'react'
import * as Popover from '@radix-ui/react-popover'
import { BookOpen } from 'lucide-react'
import type { WorkspaceEvent, LabMember } from '@/types/workspace'
import { NARRATIVE_TEMPLATES } from '@/mock/mockData'

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
}

interface NarrativeEntry {
  id: string
  agentId: string
  text: string
  timestamp: string
}

function generateNarrative(event: WorkspaceEvent, memberName: string): string {
  const key = `${event.zone}:${event.status}`
  const templates = NARRATIVE_TEMPLATES[key]
  if (templates && templates.length > 0) {
    // Pick a deterministic template based on agent_id hash
    const hash = event.agent_id.split('').reduce((acc, ch) => acc + ch.charCodeAt(0), 0)
    const template = templates[hash % templates.length]
    return template.replace('{name}', memberName)
  }
  // Fallback: generic prose
  const action = event.action.replace(/_/g, ' ')
  return `${memberName} is ${action} in the ${event.zone}.`
}

export function NarrativePanel({ events, members }: NarrativePanelProps) {
  const scrollRef = useRef<HTMLDivElement>(null)

  const memberLookup = useMemo(
    () => new Map(members?.map(m => [m.agentId, m])),
    [members]
  )

  const narrativeEntries = useMemo(() => {
    // Take last 30 events and convert to narrative
    return events.slice(-50).reverse().map((event): NarrativeEntry => {
      const member = memberLookup.get(event.agent_id)
      const name = member?.displayName ?? event.agent_id.slice(0, 10)
      return {
        id: `${event.agent_id}-${event.timestamp}-${Math.random()}`,
        agentId: event.agent_id,
        text: generateNarrative(event, name),
        timestamp: new Date(event.timestamp).toLocaleTimeString(),
      }
    })
  }, [events, memberLookup])

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

          return (
            <div key={entry.id} className="text-sm leading-relaxed">
              <span className="text-xs text-muted-foreground mr-2">{entry.timestamp}</span>
              <span className={`inline-block h-2 w-2 rounded-full ${bgClass} mr-1`} />
              {member ? (
                <AgentPopover member={member}>
                  <button className={`font-medium ${colorClass} hover:underline cursor-pointer`}>
                    {member.displayName}
                  </button>
                </AgentPopover>
              ) : (
                <span className="font-medium text-muted-foreground">{entry.agentId.slice(0, 10)}</span>
              )}
              <span className="text-muted-foreground">
                {' '}{entry.text.split(member?.displayName ?? entry.agentId.slice(0, 10)).slice(1).join(member?.displayName ?? '')}
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
            <div className="grid grid-cols-2 gap-2 text-xs">
              <div>
                <p className="text-muted-foreground">Karma</p>
                <p className="font-medium">{member.karma.toLocaleString()}</p>
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
