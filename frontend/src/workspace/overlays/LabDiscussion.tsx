/**
 * LabDiscussion -- Unified timeline merging agent activity events + human discussion.
 * Agent events appear as compact system messages; human comments as full threaded messages.
 * Replaces both NarrativePanel and HumanDiscussion.
 * Depends on: useAuth, ActivityEntry, LabMember, discussion API, mock data
 */
import { useState, useRef, useEffect, useMemo, Fragment } from 'react'
import * as Popover from '@radix-ui/react-popover'
import { MessageSquare, Send, ChevronDown, ChevronRight, ArrowUp, Anchor } from 'lucide-react'
import { Button } from '@/components/common/Button'
import { useAuth } from '@/hooks/useAuth'
import type { LabMember, ActivityEntry } from '@/types/workspace'
import { MOCK_DISCUSSION_COMMENTS, MOCK_LAB_STATE, type DiscussionComment } from '@/mock/mockData'
import { isMockMode } from '@/mock/useMockMode'
import { getLabDiscussions, postLabDiscussion } from '@/api/forum'

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

interface LabDiscussionProps {
  slug: string
  members?: LabMember[]
  activityEntries?: ActivityEntry[]
  onHighlightItem?: (itemId: string) => void
}

type TimelineEntry =
  | { kind: 'activity'; id: string; agentId: string; message: string; taskId: string | null; timestamp: string }
  | { kind: 'comment'; id: string; comment: DiscussionComment; timestamp: string }

export function LabDiscussion({ slug, members, activityEntries, onHighlightItem }: LabDiscussionProps) {
  const { user } = useAuth()
  const [comments, setComments] = useState<DiscussionComment[]>(isMockMode() ? MOCK_DISCUSSION_COMMENTS : [])
  const [input, setInput] = useState('')
  const [replyTo, setReplyTo] = useState<string | null>(null)
  const [loaded, setLoaded] = useState(false)
  const scrollRef = useRef<HTMLDivElement>(null)

  const labState = MOCK_LAB_STATE[slug] ?? []
  const itemMap = new Map(labState.map(i => [i.id, i.title]))

  const memberMap = useMemo(
    () => new Map(members?.map(m => [m.agentId, m]) ?? []),
    [members],
  )

  // Fetch discussions from backend
  useEffect(() => {
    if (!isMockMode() && !loaded) {
      getLabDiscussions(slug)
        .then(data => { setComments(data); setLoaded(true) })
        .catch(() => setLoaded(true))
    }
  }, [slug, loaded])

  // Build unified timeline
  const timeline = useMemo(() => {
    const entries: TimelineEntry[] = []

    // Add activity entries
    if (activityEntries) {
      for (const a of activityEntries) {
        entries.push({
          kind: 'activity',
          id: a.id || `act-${a.timestamp}-${Math.random()}`,
          agentId: a.agent_id ?? 'system',
          message: a.message,
          taskId: a.task_id,
          timestamp: a.timestamp,
        })
      }
    }

    // Add discussion comments (only top-level — replies rendered under parents)
    for (const c of comments) {
      if (!c.parentId) {
        entries.push({
          kind: 'comment',
          id: c.id,
          comment: c,
          timestamp: c.timestamp,
        })
      }
    }

    // Sort chronologically descending (newest first)
    entries.sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime())

    return entries.slice(0, 100)
  }, [activityEntries, comments])

  // Replies map
  const repliesByParent = useMemo(() => {
    const map = new Map<string, DiscussionComment[]>()
    for (const c of comments) {
      if (c.parentId) {
        const existing = map.get(c.parentId) ?? []
        existing.push(c)
        map.set(c.parentId, existing)
      }
    }
    return map
  }, [comments])

  // Auto-scroll to top on new entries
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = 0
    }
  }, [timeline.length])

  const handlePost = () => {
    const trimmed = input.trim()
    if (!trimmed) return

    const username = user?.username ?? 'anonymous'

    const optimisticComment: DiscussionComment = {
      id: `dc-${Date.now()}`,
      username,
      text: trimmed,
      timestamp: new Date().toISOString(),
      parentId: replyTo,
      anchorItemId: null,
      upvotes: 0,
    }
    setComments(prev => [...prev, optimisticComment])
    setInput('')
    setReplyTo(null)

    if (!isMockMode()) {
      postLabDiscussion(slug, {
        body: trimmed,
        authorName: username,
        parentId: replyTo ?? undefined,
      })
        .then(serverComment => {
          setComments(prev => prev.map(c => (c.id === optimisticComment.id ? serverComment : c)))
        })
        .catch(() => {
          setComments(prev => prev.filter(c => c.id !== optimisticComment.id))
        })
    }
  }

  const handleUpvote = (id: string) => {
    setComments(prev => prev.map(c => c.id === id ? { ...c, upvotes: c.upvotes + 1 } : c))
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handlePost()
    }
  }

  const activityCount = activityEntries?.length ?? 0
  const commentCount = comments.length

  return (
    <div className="rounded-lg border bg-card flex flex-col">
      {/* Header */}
      <div className="flex items-center gap-2 p-3 border-b">
        <MessageSquare className="h-4 w-4 text-muted-foreground" />
        <span className="text-sm font-medium">Lab Discussion</span>
        <span className="text-xs text-muted-foreground ml-auto">
          {activityCount + commentCount} entries
        </span>
      </div>

      {/* Unified timeline */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto p-3 space-y-2" style={{ maxHeight: 500 }}>
        {timeline.length === 0 && (
          <p className="text-sm text-muted-foreground italic text-center py-4">
            The lab is quiet... agents are preparing for their next research session.
          </p>
        )}
        {timeline.map(entry => {
          if (entry.kind === 'activity') {
            return (
              <ActivityRow
                key={entry.id}
                entry={entry}
                memberMap={memberMap}
                onHighlightItem={onHighlightItem}
              />
            )
          }
          return (
            <CommentThread
              key={entry.id}
              comment={entry.comment}
              replies={repliesByParent.get(entry.comment.id) ?? []}
              itemMap={itemMap}
              onReply={setReplyTo}
              onUpvote={handleUpvote}
              activeReply={replyTo}
            />
          )
        })}
      </div>

      {/* Input area */}
      <div className="border-t p-3">
        {replyTo && (
          <div className="flex items-center gap-2 mb-2 text-xs text-muted-foreground">
            <span>Replying to {comments.find(c => c.id === replyTo)?.username ?? 'comment'}</span>
            <button onClick={() => setReplyTo(null)} className="text-primary hover:underline">Cancel</button>
          </div>
        )}
        <div className="flex gap-2">
          <input
            type="text"
            placeholder="Join the discussion..."
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            className="flex-1 rounded-md border border-input bg-background px-3 py-1.5 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          />
          <Button size="sm" onClick={handlePost} disabled={!input.trim()}>
            <Send className="h-3.5 w-3.5" />
          </Button>
        </div>
      </div>
    </div>
  )
}

/** Compact single-line activity event */
function ActivityRow({
  entry,
  memberMap,
  onHighlightItem,
}: {
  entry: Extract<TimelineEntry, { kind: 'activity' }>
  memberMap: Map<string, LabMember>
  onHighlightItem?: (itemId: string) => void
}) {
  const member = memberMap.get(entry.agentId)
  const displayName = member?.displayName ?? (entry.agentId === 'system' ? 'System' : entry.agentId.slice(0, 10))
  const colorClass = member ? ARCHETYPE_COLORS[member.archetype] ?? 'text-slate-400' : 'text-slate-400'
  const bgClass = member ? ARCHETYPE_BG[member.archetype] ?? 'bg-slate-400' : 'bg-slate-400'
  const timeStr = entry.timestamp ? new Date(entry.timestamp).toLocaleTimeString() : ''

  return (
    <div className="text-xs leading-relaxed flex items-start gap-1.5 py-0.5 opacity-75 hover:opacity-100 transition-opacity">
      <span className="text-muted-foreground shrink-0 w-14 text-right">{timeStr}</span>
      <span className={`inline-block h-2 w-2 rounded-full ${bgClass} mt-1 shrink-0`} />
      {member ? (
        <AgentPopover member={member}>
          <button className={`font-medium ${colorClass} hover:underline cursor-pointer shrink-0`}>
            {displayName}
          </button>
        </AgentPopover>
      ) : (
        <span className="font-medium text-muted-foreground shrink-0">{displayName}</span>
      )}
      <span className="text-muted-foreground">
        <NarrativeText
          text={entry.message}
          taskItemId={entry.taskId}
          onHighlightItem={onHighlightItem}
        />
      </span>
    </div>
  )
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
  const parts = text.split(/\*([^*]+)\*/)
  if (parts.length === 1) return <>{text}</>

  return (
    <>
      {parts.map((part, i) => {
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

function CommentThread({
  comment,
  replies,
  itemMap,
  onReply,
  onUpvote,
  activeReply,
}: {
  comment: DiscussionComment
  replies: DiscussionComment[]
  itemMap: Map<string, string>
  onReply: (id: string) => void
  onUpvote: (id: string) => void
  activeReply: string | null
}) {
  const [showReplies, setShowReplies] = useState(true)
  const anchorTitle = comment.anchorItemId ? itemMap.get(comment.anchorItemId) : null

  return (
    <div className="text-sm bg-muted/20 rounded-md p-2.5">
      {/* Anchor badge */}
      {anchorTitle && (
        <div className="flex items-center gap-1 mb-1 text-[10px] text-primary">
          <Anchor className="h-2.5 w-2.5" />
          <span className="truncate">{anchorTitle}</span>
        </div>
      )}

      <div className="flex items-start gap-2">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="font-medium text-foreground">{comment.username}</span>
            <span className="text-xs text-muted-foreground">
              {new Date(comment.timestamp).toLocaleTimeString()}
            </span>
          </div>
          <p className="text-muted-foreground mt-0.5">{comment.text}</p>
          <div className="flex items-center gap-3 mt-1">
            <button
              onClick={() => onUpvote(comment.id)}
              className="flex items-center gap-1 text-xs text-muted-foreground hover:text-primary transition-colors"
            >
              <ArrowUp className="h-3 w-3" />
              {comment.upvotes}
            </button>
            <button
              onClick={() => onReply(comment.id)}
              className={`text-xs transition-colors ${activeReply === comment.id ? 'text-primary' : 'text-muted-foreground hover:text-primary'}`}
            >
              Reply
            </button>
          </div>
        </div>
      </div>

      {/* Replies */}
      {replies.length > 0 && (
        <div className="ml-4 mt-2">
          <button
            onClick={() => setShowReplies(!showReplies)}
            className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground mb-1"
          >
            {showReplies ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
            {replies.length} {replies.length === 1 ? 'reply' : 'replies'}
          </button>
          {showReplies && (
            <div className="space-y-2 border-l-2 border-muted pl-3">
              {replies.map(reply => (
                <div key={reply.id} className="text-sm">
                  <div className="flex items-center gap-2">
                    <span className="font-medium text-foreground">{reply.username}</span>
                    <span className="text-xs text-muted-foreground">
                      {new Date(reply.timestamp).toLocaleTimeString()}
                    </span>
                  </div>
                  <p className="text-muted-foreground mt-0.5">{reply.text}</p>
                  <button
                    onClick={() => onUpvote(reply.id)}
                    className="flex items-center gap-1 text-xs text-muted-foreground hover:text-primary transition-colors mt-1"
                  >
                    <ArrowUp className="h-3 w-3" />
                    {reply.upvotes}
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
