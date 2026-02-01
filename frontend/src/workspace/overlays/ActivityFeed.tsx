/**
 * ActivityFeed -- React overlay displaying a scrollable, real-time activity event feed.
 * Shows agent display names instead of raw IDs when members are provided.
 * Depends on: WorkspaceEvent type, LabMember type, lucide-react
 */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type { WorkspaceEvent } from '@/types/workspace'
import type { LabMember } from '@/types/workspace'
import { Activity } from 'lucide-react'

const ARCHETYPE_COLORS: Record<string, string> = {
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

interface ActivityEntry {
  id: string
  event: WorkspaceEvent
  displayTime: string
}

interface ActivityFeedProps {
  events: WorkspaceEvent[]
  members?: LabMember[]
}

export function ActivityFeed({ events, members }: ActivityFeedProps) {
  const [entries, setEntries] = useState<ActivityEntry[]>([])
  const scrollRef = useRef<HTMLDivElement>(null)
  const processedRef = useRef(0)

  const memberLookup = useMemo(
    () => new Map(members?.map(m => [m.agentId, m])),
    [members]
  )

  const addEntry = useCallback((event: WorkspaceEvent) => {
    const entry: ActivityEntry = {
      id: `${event.agent_id}-${event.timestamp}-${Math.random()}`,
      event,
      displayTime: new Date(event.timestamp).toLocaleTimeString(),
    }
    setEntries(prev => [entry, ...prev].slice(0, 50)) // Keep last 50
  }, [])

  useEffect(() => {
    // Guard: if events array was replaced/truncated, reset cursor
    const cursor = Math.min(processedRef.current, events.length)
    const newEvents = events.slice(cursor)
    for (const event of newEvents) {
      addEntry(event)
    }
    processedRef.current = events.length
  }, [events, addEntry])

  // Auto-scroll to top when new entries arrive (newest are prepended)
  useEffect(() => {
    if (scrollRef.current && entries.length > 0) {
      scrollRef.current.scrollTop = 0
    }
  }, [entries.length])

  const actionLabel = (action: string) => {
    return action.replace(/_/g, ' ').replace(/moved to /, '→ ')
  }

  return (
    <div className="absolute left-0 bottom-0 w-72 max-h-64 bg-card/90 backdrop-blur border-t border-r rounded-tr-lg shadow-lg z-30 flex flex-col">
      {/* Header */}
      <div className="flex items-center gap-2 p-2 border-b">
        <Activity className="h-3.5 w-3.5 text-muted-foreground" />
        <span className="text-xs font-medium">Activity</span>
        <span className="text-xs text-muted-foreground ml-auto">{entries.length}</span>
      </div>

      {/* Scrollable list */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto p-2 space-y-1">
        {entries.length === 0 && (
          <p className="text-xs text-muted-foreground italic p-2">Waiting for activity...</p>
        )}
        {entries.map(entry => {
          const member = memberLookup.get(entry.event.agent_id)
          const colorClass = member ? ARCHETYPE_COLORS[member.archetype] ?? 'bg-slate-400' : 'bg-slate-400'
          return (
            <div
              key={entry.id}
              className="text-xs p-1.5 rounded hover:bg-muted/50 transition-colors cursor-default"
            >
              <div className="flex items-center gap-1.5">
                <span className={`inline-block h-2 w-2 rounded-full flex-shrink-0 ${colorClass}`} />
                <span className="font-medium text-foreground truncate max-w-[120px]">
                  {member?.displayName ?? entry.event.agent_id.slice(0, 10)}
                </span>
                <span className="text-muted-foreground truncate">
                  {actionLabel(entry.event.action)}
                </span>
              </div>
              <div className="flex items-center gap-1.5 mt-0.5 text-muted-foreground ml-3.5">
                <span>{entry.event.zone}</span>
                <span>·</span>
                <span>{entry.displayTime}</span>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
