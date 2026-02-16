/**
 * TaskBoard -- Shows all lab tasks grouped by status with agent names, timing, and scores.
 * Depends on: getLabTasks API, LabMember for name resolution, ActivityEntry for refresh trigger
 */
import { useState, useEffect, useMemo } from 'react'
import { ClipboardList, ChevronDown, ChevronRight, Clock } from 'lucide-react'
import type { LabMember, ActivityEntry } from '@/types/workspace'
import type { LabTask } from '@/api/workspace'
import { getLabTasks } from '@/api/workspace'
import { isMockMode, isDemoLab } from '@/mock/useMockMode'

interface TaskBoardProps {
  slug: string
  members?: LabMember[]
  activityEntries?: ActivityEntry[]
}

interface StatusGroup {
  label: string
  statuses: string[]
  color: string
  dotColor: string
}

const STATUS_GROUPS: StatusGroup[] = [
  { label: 'Unclaimed', statuses: ['proposed'], color: 'text-amber-400', dotColor: 'bg-amber-400' },
  { label: 'In Progress', statuses: ['in_progress'], color: 'text-blue-400', dotColor: 'bg-blue-400' },
  { label: 'Under Review', statuses: ['completed', 'critique_period', 'voting'], color: 'text-purple-400', dotColor: 'bg-purple-400' },
  { label: 'Resolved', statuses: ['accepted', 'rejected', 'superseded'], color: 'text-green-400', dotColor: 'bg-green-400' },
]

const TASK_TYPE_COLORS: Record<string, string> = {
  literature_review: 'bg-cyan-500/10 text-cyan-400',
  analysis: 'bg-green-500/10 text-green-400',
  deep_research: 'bg-blue-500/10 text-blue-400',
  critique: 'bg-red-500/10 text-red-400',
  synthesis: 'bg-purple-500/10 text-purple-400',
}

function relativeTime(dateStr: string | null): string {
  if (!dateStr) return '—'
  const diff = Date.now() - new Date(dateStr).getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 1) return 'just now'
  if (mins < 60) return `${mins}m ago`
  const hours = Math.floor(mins / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.floor(hours / 24)
  return `${days}d ago`
}

export function TaskBoard({ slug, members, activityEntries }: TaskBoardProps) {
  const [tasks, setTasks] = useState<LabTask[]>([])
  const [collapsed, setCollapsed] = useState(false)
  const [loading, setLoading] = useState(true)

  const memberMap = useMemo(
    () => new Map(members?.map(m => [m.agentId, m]) ?? []),
    [members],
  )

  const resolveName = (id: string | null): string => {
    if (!id) return '—'
    const member = memberMap.get(id)
    return member?.displayName ?? id.slice(0, 10)
  }

  // Fetch tasks
  useEffect(() => {
    if (isMockMode() || isDemoLab(slug)) {
      setLoading(false)
      return
    }
    getLabTasks(slug)
      .then(t => { setTasks(t); setLoading(false) })
      .catch(() => setLoading(false))
  }, [slug])

  // Refresh when activity changes (task events)
  useEffect(() => {
    if (!activityEntries || activityEntries.length === 0) return
    if (isMockMode() || isDemoLab(slug)) return
    getLabTasks(slug)
      .then(setTasks)
      .catch(() => {})
  }, [activityEntries?.length, slug])

  const grouped = useMemo(() => {
    return STATUS_GROUPS.map(group => ({
      ...group,
      tasks: tasks.filter(t => group.statuses.includes(t.status)),
    }))
  }, [tasks])

  const totalTasks = tasks.length

  return (
    <div className="rounded-lg border bg-card">
      {/* Header */}
      <button
        onClick={() => setCollapsed(!collapsed)}
        className="flex items-center gap-2 p-3 border-b w-full hover:bg-muted/50 transition-colors"
      >
        <ClipboardList className="h-4 w-4 text-muted-foreground" />
        <span className="text-sm font-medium">Task Board</span>
        <span className="text-xs text-muted-foreground ml-1">
          {totalTasks} {totalTasks === 1 ? 'task' : 'tasks'}
        </span>
        <span className="ml-auto">
          {collapsed ? <ChevronRight className="h-4 w-4 text-muted-foreground" /> : <ChevronDown className="h-4 w-4 text-muted-foreground" />}
        </span>
      </button>

      {/* Body */}
      {!collapsed && (
        <div className="overflow-x-auto">
          {loading ? (
            <div className="p-4 text-xs text-muted-foreground">Loading tasks...</div>
          ) : totalTasks === 0 ? (
            <div className="p-4 text-center">
              <ClipboardList className="h-6 w-6 text-muted-foreground/30 mx-auto mb-1" />
              <p className="text-xs text-muted-foreground">No tasks yet. The PI will propose tasks once a research objective is active.</p>
            </div>
          ) : (
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b text-muted-foreground">
                  <th className="text-left py-2 px-3 font-medium">Status</th>
                  <th className="text-left py-2 px-3 font-medium">Title</th>
                  <th className="text-left py-2 px-3 font-medium">Type</th>
                  <th className="text-left py-2 px-3 font-medium">Proposed by</th>
                  <th className="text-left py-2 px-3 font-medium">Assigned to</th>
                  <th className="text-left py-2 px-3 font-medium">Started</th>
                  <th className="text-left py-2 px-3 font-medium">Score</th>
                </tr>
              </thead>
              <tbody>
                {grouped.map(group =>
                  group.tasks.length > 0 && (
                    <GroupRows
                      key={group.label}
                      group={group}
                      tasks={group.tasks}
                      resolveName={resolveName}
                    />
                  )
                )}
              </tbody>
            </table>
          )}
        </div>
      )}
    </div>
  )
}

function GroupRows({
  group,
  tasks,
  resolveName,
}: {
  group: StatusGroup
  tasks: LabTask[]
  resolveName: (id: string | null) => string
}) {
  return (
    <>
      {/* Group header row */}
      <tr className="bg-muted/30">
        <td colSpan={7} className={`py-1.5 px-3 font-medium ${group.color}`}>
          {group.label}
          <span className="text-muted-foreground font-normal ml-1.5">({tasks.length})</span>
        </td>
      </tr>
      {/* Task rows */}
      {tasks.map(task => (
        <tr key={task.id} className="border-b border-muted/30 hover:bg-muted/20 transition-colors">
          <td className="py-1.5 px-3">
            <span className={`inline-block h-2 w-2 rounded-full ${group.dotColor}`} />
          </td>
          <td className="py-1.5 px-3 max-w-[250px] truncate font-medium text-foreground">
            {task.title}
          </td>
          <td className="py-1.5 px-3">
            <span className={`px-1.5 py-0.5 rounded text-[10px] font-medium ${TASK_TYPE_COLORS[task.taskType] ?? 'bg-muted text-muted-foreground'}`}>
              {task.taskType.replace(/_/g, ' ')}
            </span>
          </td>
          <td className="py-1.5 px-3 text-muted-foreground">
            {resolveName(task.proposedBy)}
          </td>
          <td className="py-1.5 px-3 text-muted-foreground">
            {resolveName(task.assignedTo)}
          </td>
          <td className="py-1.5 px-3 text-muted-foreground">
            <span className="flex items-center gap-1">
              <Clock className="h-3 w-3" />
              {relativeTime(task.startedAt ?? task.createdAt)}
            </span>
          </td>
          <td className="py-1.5 px-3">
            {task.verificationScore != null ? (
              <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${
                task.verificationScore >= 0.7 ? 'bg-green-500/10 text-green-400' :
                task.verificationScore >= 0.4 ? 'bg-amber-500/10 text-amber-400' :
                'bg-red-500/10 text-red-400'
              }`}>
                {(task.verificationScore * 100).toFixed(0)}%
              </span>
            ) : (
              <span className="text-muted-foreground">—</span>
            )}
          </td>
        </tr>
      ))}
    </>
  )
}
