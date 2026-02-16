/**
 * EmbeddedLabCard -- Rendered inside a forum post card as a footer section
 * when the post has a linked lab. Shows status, agents, tasks, progress, and workspace link.
 */
import { Link } from 'react-router-dom'
import { cn } from '@/lib/utils'
import { Users, ArrowRight } from 'lucide-react'
import type { ForumPostLab } from '@/types/forum'

function relativeTime(dateStr: string | null): string {
  if (!dateStr) return 'No activity yet'
  const diff = Date.now() - new Date(dateStr).getTime()
  const mins = Math.floor(diff / 60_000)
  if (mins < 1) return 'Just now'
  if (mins < 60) return `${mins}m ago`
  const hours = Math.floor(mins / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.floor(hours / 24)
  return `${days}d ago`
}

const STATUS_CONFIG: Record<string, { label: string; dotClass: string; labelClass: string }> = {
  active: {
    label: 'Active',
    dotClass: 'bg-green-500 animate-pulse',
    labelClass: 'text-green-600 dark:text-green-400',
  },
  completed: {
    label: 'Completed',
    dotClass: 'bg-blue-500',
    labelClass: 'text-blue-600 dark:text-blue-400',
  },
  paused: {
    label: 'Paused',
    dotClass: 'bg-yellow-500',
    labelClass: 'text-yellow-600 dark:text-yellow-400',
  },
}

export function EmbeddedLabCard({ lab, isSample }: { lab: ForumPostLab; isSample?: boolean }) {
  const statusCfg = STATUS_CONFIG[lab.status] ?? STATUS_CONFIG.paused

  // Progress based on actual task completion
  const rawPct = lab.taskCount > 0
    ? Math.round((lab.tasksCompleted / lab.taskCount) * 100)
    : 0
  // Only show 100% when truly done
  const progressPct = (lab.status === 'completed' || (lab.taskCount > 0 && lab.tasksAccepted === lab.taskCount))
    ? 100
    : Math.min(99, rawPct)

  // Build task breakdown segments
  const segments: string[] = []
  if (lab.tasksInProgress > 0) segments.push(`${lab.tasksInProgress} active`)
  if (lab.tasksCompleted > 0) segments.push(`${lab.tasksCompleted} done`)
  if (lab.taskCount > 0 && lab.tasksCompleted === 0 && lab.tasksInProgress === 0) {
    segments.push(`${lab.taskCount} proposed`)
  }

  return (
    <div className="mt-3 mx-4 mb-4 p-3 rounded-md bg-blue-50 dark:bg-slate-800/50 border border-dashed border-slate-200 dark:border-slate-700">
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2 min-w-0">
          {/* Status dot + label */}
          <span
            className={cn('flex h-2 w-2 rounded-full flex-shrink-0', statusCfg.dotClass)}
          />
          <span className={cn('text-xs font-medium flex-shrink-0', statusCfg.labelClass)}>
            {statusCfg.label}
          </span>

          {/* Lab name */}
          <Link
            to={`/labs/${lab.slug}/workspace`}
            className="text-sm font-medium truncate hover:text-primary transition-colors"
            onClick={e => e.stopPropagation()}
          >
            {lab.name}
          </Link>
        </div>

        <Link
          to={`/labs/${lab.slug}/workspace`}
          className="flex items-center gap-1 text-xs text-primary hover:underline flex-shrink-0"
          onClick={e => e.stopPropagation()}
        >
          View Lab
          <ArrowRight className="h-3 w-3" />
        </Link>
      </div>

      {/* Stats row */}
      <div className="flex items-center gap-3 mt-2 text-xs text-muted-foreground">
        <span className="flex items-center gap-1">
          <Users className="h-3 w-3" />
          {lab.agentCount} agents
        </span>
        {segments.length > 0 && (
          <span>{segments.join(' \u00b7 ')}</span>
        )}
        <span className="ml-auto">{relativeTime(lab.lastActivityAt)}</span>
        {isSample && (
          <span className="inline-flex items-center rounded-full bg-amber-100 dark:bg-amber-900/30 px-1.5 py-0.5 text-[10px] font-medium text-amber-700 dark:text-amber-400">
            Demo
          </span>
        )}
      </div>

      {/* Progress bar */}
      {lab.taskCount > 0 && (
        <div className="flex items-center gap-2 mt-2">
          <div className="flex-1 h-1.5 rounded-full bg-slate-200 dark:bg-slate-700 overflow-hidden">
            <div
              className={cn(
                'h-full rounded-full transition-all',
                progressPct === 100 ? 'bg-green-500' : 'bg-primary',
              )}
              style={{ width: `${progressPct}%` }}
            />
          </div>
          <span className="text-[10px] text-muted-foreground font-medium">{progressPct}%</span>
        </div>
      )}
    </div>
  )
}
