/**
 * HumanComments -- Below-workspace panel for human observers to post comments.
 * Uses local state + seed comments from mock data.
 * Depends on: useAuth hook, MOCK_COMMENTS
 */
import { useState, useRef, useEffect } from 'react'
import { MessageSquare, Send } from 'lucide-react'
import { Button } from '@/components/common/Button'
import { useAuth } from '@/hooks/useAuth'
import { MOCK_COMMENTS, type MockComment } from '@/mock/mockData'

interface HumanCommentsProps {
  slug: string
}

export function HumanComments({ slug: _slug }: HumanCommentsProps) {
  const { user } = useAuth()
  const [comments, setComments] = useState<MockComment[]>(MOCK_COMMENTS)
  const [input, setInput] = useState('')
  const scrollRef = useRef<HTMLDivElement>(null)

  // Scroll to bottom when new comments added
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [comments.length])

  const handlePost = () => {
    const trimmed = input.trim()
    if (!trimmed) return

    const newComment: MockComment = {
      id: `hc-${Date.now()}`,
      username: user?.username ?? 'anonymous',
      text: trimmed,
      timestamp: new Date().toISOString(),
    }
    setComments(prev => [...prev, newComment])
    setInput('')
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handlePost()
    }
  }

  return (
    <div className="rounded-lg border bg-card flex flex-col">
      {/* Header */}
      <div className="flex items-center gap-2 p-3 border-b">
        <MessageSquare className="h-4 w-4 text-muted-foreground" />
        <span className="text-sm font-medium">Comments</span>
        <span className="text-xs text-muted-foreground ml-auto">{comments.length}</span>
      </div>

      {/* Comment list */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto p-3 space-y-3" style={{ maxHeight: 240 }}>
        {comments.map(comment => (
          <div key={comment.id} className="text-sm">
            <div className="flex items-center gap-2">
              <span className="font-medium text-foreground">{comment.username}</span>
              <span className="text-xs text-muted-foreground">
                {new Date(comment.timestamp).toLocaleTimeString()}
              </span>
            </div>
            <p className="text-muted-foreground mt-0.5">{comment.text}</p>
          </div>
        ))}
      </div>

      {/* Input area */}
      <div className="border-t p-3">
        <div className="flex gap-2">
          <input
            type="text"
            placeholder="Share your thoughts..."
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
