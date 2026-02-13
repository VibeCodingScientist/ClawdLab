/**
 * CommunityIdeas -- Panel showing forum posts and suggestions linked to a lab.
 * Shows the originating forum post + any community suggestions claimed by this lab.
 * Depends on: getLabSuggestions API, lucide-react
 */
import { useState, useEffect } from 'react'
import { Lightbulb, MessageCircle, ArrowUp } from 'lucide-react'
import { getLabSuggestions, type LabSuggestion } from '@/api/forum'
import { isMockMode } from '@/mock/useMockMode'

interface CommunityIdeasProps {
  slug: string
}

export function CommunityIdeas({ slug }: CommunityIdeasProps) {
  const [suggestions, setSuggestions] = useState<LabSuggestion[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (isMockMode()) {
      setLoading(false)
      return
    }

    getLabSuggestions(slug)
      .then(data => {
        setSuggestions(data)
        setLoading(false)
      })
      .catch(err => {
        setError(err instanceof Error ? err.message : 'Failed to load')
        setLoading(false)
      })
  }, [slug])

  if (loading) {
    return (
      <div className="rounded-lg border bg-card p-4">
        <div className="flex items-center gap-2 mb-3">
          <Lightbulb className="h-4 w-4 text-amber-400" />
          <span className="text-sm font-medium">Community Ideas</span>
        </div>
        <div className="text-xs text-muted-foreground">Loading suggestions...</div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="rounded-lg border bg-card p-4">
        <div className="flex items-center gap-2 mb-3">
          <Lightbulb className="h-4 w-4 text-amber-400" />
          <span className="text-sm font-medium">Community Ideas</span>
        </div>
        <div className="text-xs text-destructive">{error}</div>
      </div>
    )
  }

  return (
    <div className="rounded-lg border bg-card flex flex-col">
      {/* Header */}
      <div className="flex items-center gap-2 p-3 border-b">
        <Lightbulb className="h-4 w-4 text-amber-400" />
        <span className="text-sm font-medium">Community Ideas</span>
        <span className="text-xs text-muted-foreground ml-auto">
          {suggestions.length} {suggestions.length === 1 ? 'idea' : 'ideas'}
        </span>
      </div>

      {/* Content */}
      <div className="overflow-y-auto p-3 space-y-3" style={{ maxHeight: 300 }}>
        {suggestions.length === 0 ? (
          <div className="text-center py-6">
            <Lightbulb className="h-8 w-8 text-muted-foreground/30 mx-auto mb-2" />
            <p className="text-xs text-muted-foreground">
              No community suggestions yet.
            </p>
            <p className="text-xs text-muted-foreground mt-1">
              Use "Suggest to Lab" to share an idea.
            </p>
          </div>
        ) : (
          suggestions.map(suggestion => (
            <SuggestionCard key={suggestion.id} suggestion={suggestion} />
          ))
        )}
      </div>
    </div>
  )
}

function SuggestionCard({ suggestion }: { suggestion: LabSuggestion }) {
  const [expanded, setExpanded] = useState(false)
  const isLong = suggestion.body.length > 150

  return (
    <div className="rounded-md border border-muted/50 p-2.5 hover:border-muted transition-colors">
      <div className="flex items-start gap-2">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span className="text-xs font-medium text-foreground truncate">
              {suggestion.title}
            </span>
            {suggestion.source === 'forum' && (
              <span className="text-[10px] px-1.5 py-0.5 rounded bg-primary/10 text-primary shrink-0">
                Forum
              </span>
            )}
          </div>

          <p className="text-xs text-muted-foreground">
            {expanded || !isLong
              ? suggestion.body
              : `${suggestion.body.slice(0, 150)}...`}
          </p>
          {isLong && (
            <button
              onClick={() => setExpanded(!expanded)}
              className="text-[10px] text-primary hover:underline mt-1"
            >
              {expanded ? 'Show less' : 'Read more'}
            </button>
          )}

          <div className="flex items-center gap-3 mt-1.5 text-[10px] text-muted-foreground">
            <span>{suggestion.authorName}</span>
            <span className="flex items-center gap-0.5">
              <ArrowUp className="h-2.5 w-2.5" />
              {suggestion.upvotes}
            </span>
            <span className="flex items-center gap-0.5">
              <MessageCircle className="h-2.5 w-2.5" />
              {suggestion.commentCount}
            </span>
            <span>
              {new Date(suggestion.createdAt).toLocaleDateString()}
            </span>
            {suggestion.status !== 'open' && (
              <span className={`px-1 py-0.5 rounded ${
                suggestion.status === 'claimed' ? 'bg-green-500/10 text-green-500' : 'bg-muted'
              }`}>
                {suggestion.status}
              </span>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
