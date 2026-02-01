/**
 * RoundtablePanel -- React overlay displaying the research roundtable debate view with votes.
 * Depends on: @tanstack/react-query, workspace API, ARCHETYPE_CONFIGS
 */
import { useQuery } from '@tanstack/react-query'
import { getRoundtable } from '@/api/workspace'
import { ARCHETYPE_CONFIGS, type RoleArchetype } from '../game/config/archetypes'
import { X, ThumbsUp, ThumbsDown, Minus } from 'lucide-react'
import { Button } from '@/components/common/Button'
import { getErrorMessage } from '@/types'

interface RoundtablePanelProps {
  slug: string
  researchItemId: string
  onClose: () => void
}

const ENTRY_TYPE_STYLES: Record<string, { bg: string; label: string }> = {
  proposal:  { bg: 'bg-blue-500/10 border-blue-500/20', label: 'Proposal' },
  argument:  { bg: 'bg-purple-500/10 border-purple-500/20', label: 'Argument' },
  evidence:  { bg: 'bg-green-500/10 border-green-500/20', label: 'Evidence' },
  vote:      { bg: 'bg-amber-500/10 border-amber-500/20', label: 'Vote' },
  rebuttal:  { bg: 'bg-red-500/10 border-red-500/20', label: 'Rebuttal' },
}

export function RoundtablePanel({ slug, researchItemId, onClose }: RoundtablePanelProps) {
  const { data: roundtable, isLoading, error } = useQuery({
    queryKey: ['roundtable', slug, researchItemId],
    queryFn: () => getRoundtable(slug, researchItemId),
    enabled: !!researchItemId,
  })

  return (
    <div className="absolute inset-0 bg-card/98 backdrop-blur z-50 overflow-y-auto">
      {/* Header */}
      <div className="sticky top-0 bg-card border-b p-4 flex items-center justify-between">
        <h3 className="font-semibold">Roundtable Discussion</h3>
        <Button variant="ghost" size="icon" onClick={onClose}>
          <X className="h-4 w-4" />
        </Button>
      </div>

      {isLoading && (
        <div className="flex items-center justify-center p-8">
          <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-primary" />
        </div>
      )}

      {error && (
        <div className="p-4 text-destructive text-sm">{getErrorMessage(error)}</div>
      )}

      {roundtable && (
        <div className="p-4 space-y-4">
          {/* Vote tally */}
          <div className="flex items-center gap-4 p-3 bg-muted/50 rounded-lg">
            <span className="text-sm font-medium">Votes:</span>
            <span className="flex items-center gap-1 text-green-500 text-sm">
              <ThumbsUp className="h-3.5 w-3.5" /> {roundtable.voteTally.approve}
            </span>
            <span className="flex items-center gap-1 text-red-500 text-sm">
              <ThumbsDown className="h-3.5 w-3.5" /> {roundtable.voteTally.reject}
            </span>
            <span className="flex items-center gap-1 text-muted-foreground text-sm">
              <Minus className="h-3.5 w-3.5" /> {roundtable.voteTally.abstain}
            </span>
            {roundtable.resolved && (
              <span className="ml-auto text-xs bg-green-500/20 text-green-500 px-2 py-0.5 rounded">
                Resolved
              </span>
            )}
          </div>

          {/* Entries */}
          <div className="space-y-3">
            {roundtable.entries.map(entry => {
              const style = ENTRY_TYPE_STYLES[entry.entryType] ?? ENTRY_TYPE_STYLES.argument
              const config = ARCHETYPE_CONFIGS[entry.archetype as RoleArchetype]

              return (
                <div key={entry.id} className={`p-3 rounded-lg border ${style.bg}`}>
                  <div className="flex items-center gap-2 mb-2">
                    <div
                      className="w-2 h-2 rounded-full"
                      style={{ backgroundColor: config?.color ?? '#888' }}
                    />
                    <span className="text-sm font-medium">{entry.displayName}</span>
                    <span className="text-xs text-muted-foreground">
                      {config?.label}
                    </span>
                    <span className="ml-auto text-xs bg-muted px-1.5 py-0.5 rounded">
                      {style.label}
                    </span>
                    {entry.vote && (
                      <span className={`text-xs px-1.5 py-0.5 rounded ${
                        entry.vote === 'approve' ? 'bg-green-500/20 text-green-500' :
                        entry.vote === 'reject' ? 'bg-red-500/20 text-red-500' :
                        'bg-muted text-muted-foreground'
                      }`}>
                        {entry.vote}
                      </span>
                    )}
                  </div>
                  <p className="text-sm leading-relaxed">{entry.content}</p>
                  <p className="text-xs text-muted-foreground mt-2">
                    {new Date(entry.timestamp).toLocaleString()}
                  </p>
                </div>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}
