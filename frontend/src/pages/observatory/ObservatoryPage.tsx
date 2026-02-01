/**
 * ObservatoryPage -- Three-layer observatory view: radar -> lab overview -> workspace drill-down.
 * Depends on: ResearchRadar, LabOverview, GlobalFeed, LabWorkspace
 */
import { useCallback, useMemo, useState } from 'react'
import { ResearchRadar } from '@/components/observatory/ResearchRadar'
import { LabOverview } from '@/components/observatory/LabOverview'
import { GlobalFeed } from '@/components/feed/GlobalFeed'
import { LabWorkspace } from '@/workspace/LabWorkspace'
import { ChevronRight, ArrowLeft } from 'lucide-react'
import { Button } from '@/components/common/Button'

type Layer =
  | { type: 'radar' }
  | { type: 'lab'; slug: string }
  | { type: 'workspace'; slug: string }

export function ObservatoryPage() {
  const [layer, setLayer] = useState<Layer>({ type: 'radar' })

  const handleLabSelect = useCallback((slug: string) => {
    setLayer({ type: 'lab', slug })
  }, [])

  const breadcrumbs = useMemo(() => {
    const crumbs: Array<{ label: string; onClick?: () => void }> = [
      { label: 'Observatory', onClick: () => setLayer({ type: 'radar' }) },
    ]

    if (layer.type === 'lab' || layer.type === 'workspace') {
      crumbs.push({
        label: layer.slug.replace(/-/g, ' '),
        onClick: layer.type === 'workspace'
          ? () => setLayer({ type: 'lab', slug: layer.slug })
          : undefined,
      })
    }

    if (layer.type === 'workspace') {
      crumbs.push({ label: 'Workspace' })
    }

    return crumbs
  }, [layer])

  return (
    <div className="space-y-4">
      {/* Breadcrumbs */}
      <div className="flex items-center gap-1 text-sm">
        {layer.type !== 'radar' && (
          <Button
            variant="ghost"
            size="sm"
            className="mr-2 h-7 px-2"
            onClick={() => {
              if (layer.type === 'workspace') {
                setLayer({ type: 'lab', slug: layer.slug })
              } else {
                setLayer({ type: 'radar' })
              }
            }}
          >
            <ArrowLeft className="h-3.5 w-3.5" />
          </Button>
        )}
        {breadcrumbs.map((crumb, i) => (
          <span key={i} className="flex items-center gap-1">
            {i > 0 && <ChevronRight className="h-3.5 w-3.5 text-muted-foreground" />}
            {crumb.onClick ? (
              <button
                onClick={crumb.onClick}
                className="text-muted-foreground hover:text-foreground transition-colors capitalize"
              >
                {crumb.label}
              </button>
            ) : (
              <span className="text-foreground font-medium capitalize">{crumb.label}</span>
            )}
          </span>
        ))}
      </div>

      {/* Layer content */}
      {layer.type === 'radar' && (
        <div className="grid grid-cols-3 gap-4">
          <div className="col-span-2 bg-card rounded-lg border p-4" style={{ minHeight: 500 }}>
            <h2 className="text-lg font-semibold mb-4">Research Radar</h2>
            <ResearchRadar onLabSelect={handleLabSelect} />
          </div>
          <div className="border rounded-lg p-4 bg-card">
            <GlobalFeed />
          </div>
        </div>
      )}

      {layer.type === 'lab' && (
        <LabOverview
          slug={layer.slug}
          onOpenWorkspace={() => setLayer({ type: 'workspace', slug: layer.slug })}
        />
      )}

      {layer.type === 'workspace' && (
        <LabWorkspace slug={layer.slug} />
      )}
    </div>
  )
}
