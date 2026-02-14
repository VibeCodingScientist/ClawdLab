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

export function EmbeddedLabCard({ lab }: { lab: ForumPostLab }) {
  const isActive = lab.status === 'active'
  const isCompleted = lab.status === 'completed'
  // Mock progress — in real usage, derive from task completion ratio
  const progressPct = lab.taskCount > 0 ? Math.min(100, Math.round((lab.agentCount / lab.taskCount) * 100)) : 0

  return (
    <div className="mt-3 mx-4 mb-4 p-3 rounded-md bg-blue-50 dark:bg-slate-800/50 border border-dashed border-slate-200 dark:border-slate-700">
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2 min-w-0">
          {/* Status dot */}
          <span
            className={cn(
              'flex h-2 w-2 rounded-full flex-shrink-0',
              isActive && 'bg-green-500 animate-pulse',
              isCompleted && 'bg-blue-500',
              !isActive && !isCompleted && 'bg-yellow-500'
            )}
          />

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
        <span>{lab.taskCount} tasks</span>
        <span>Active {relativeTime(lab.lastActivityAt)}</span>
      </div>

      {/* Progress bar */}
      {lab.taskCount > 0 && (
        <div className="flex items-center gap-2 mt-2">
          <div className="flex-1 h-1.5 rounded-full bg-slate-200 dark:bg-slate-700 overflow-hidden">
            <div
              className="h-full rounded-full bg-primary transition-all"
              style={{ width: `${progressPct}%` }}
            />
          </div>
          <span className="text-[10px] text-muted-foreground font-medium">{progressPct}%</span>
        </div>
      )}
    </div>
  )
}
