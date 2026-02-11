/**
 * HumanDiscussion -- Threaded discussion panel for human observers.
 * Supports replies (max 2 levels), optional research anchors, and upvotes.
 * Depends on: useAuth, MOCK_DISCUSSION_COMMENTS, MOCK_LAB_STATE
 */
import { useState, useRef, useEffect } from 'react'
import { MessageSquare, Send, ChevronDown, ChevronRight, ArrowUp, Anchor } from 'lucide-react'
import { Button } from '@/components/common/Button'
import { useAuth } from '@/hooks/useAuth'
import { MOCK_DISCUSSION_COMMENTS, MOCK_LAB_STATE, type DiscussionComment } from '@/mock/mockData'

interface HumanDiscussionProps {
  slug: string
}

export function HumanDiscussion({ slug }: HumanDiscussionProps) {
  const { user } = useAuth()
  const [comments, setComments] = useState<DiscussionComment[]>(MOCK_DISCUSSION_COMMENTS)
  const [input, setInput] = useState('')
  const [replyTo, setReplyTo] = useState<string | null>(null)
  const scrollRef = useRef<HTMLDivElement>(null)

  const labState = MOCK_LAB_STATE[slug] ?? []
  const itemMap = new Map(labState.map(i => [i.id, i.title]))

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [comments.length])

  const handlePost = () => {
    const trimmed = input.trim()
    if (!trimmed) return

    const newComment: DiscussionComment = {
      id: `dc-${Date.now()}`,
      username: user?.username ?? 'anonymous',
      text: trimmed,
      timestamp: new Date().toISOString(),
      parentId: replyTo,
      anchorItemId: null,
      upvotes: 0,
    }
    setComments(prev => [...prev, newComment])
    setInput('')
    setReplyTo(null)
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

  // Build thread structure
  const topLevel = comments.filter(c => !c.parentId)
  const repliesByParent = new Map<string, DiscussionComment[]>()
  for (const c of comments) {
    if (c.parentId) {
      const existing = repliesByParent.get(c.parentId) ?? []
      existing.push(c)
      repliesByParent.set(c.parentId, existing)
    }
  }

  return (
    <div className="rounded-lg border bg-card flex flex-col">
      {/* Header */}
      <div className="flex items-center gap-2 p-3 border-b">
        <MessageSquare className="h-4 w-4 text-muted-foreground" />
        <span className="text-sm font-medium">Scientist Discussion</span>
        <span className="text-xs text-muted-foreground ml-auto">{comments.length}</span>
      </div>

      {/* Thread list */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto p-3 space-y-3" style={{ maxHeight: 300 }}>
        {topLevel.map(comment => (
          <CommentThread
            key={comment.id}
            comment={comment}
            replies={repliesByParent.get(comment.id) ?? []}
            itemMap={itemMap}
            onReply={setReplyTo}
            onUpvote={handleUpvote}
            activeReply={replyTo}
          />
        ))}
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
    <div className="text-sm">
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
