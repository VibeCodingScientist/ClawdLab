/**
 * LabStatePanel -- Collapsible full-width panel showing structured research state.
 * Displays lab state items with status icons, verification scores, research journey
 * timeline, audit trail for established items, and cross-panel highlight support.
 * Depends on: LabStateItem type, MOCK_LAB_STATE, lucide-react, getDomainStyle, DOMAIN_PROFILES
 */
import { useState, useEffect, useRef } from 'react'
import { ChevronDown, ChevronRight, CheckCircle, Search, Swords, Lightbulb, ArrowRight, Shield } from 'lucide-react'
import type { LabStateItem, LabStateStatus, EvidenceEntry, SignatureEntry } from '@/types/workspace'
import { MOCK_LAB_STATE } from '@/mock/mockData'
import { getDomainStyle, DOMAIN_PROFILES } from '@/utils/domainStyles'

const STATUS_CONFIG: Record<LabStateStatus, { icon: React.ReactNode; label: string; color: string }> = {
  established:         { icon: <CheckCircle className="h-3.5 w-3.5" />, label: 'Established',         color: 'text-green-500' },
  under_investigation: { icon: <Search className="h-3.5 w-3.5" />,      label: 'Under Investigation', color: 'text-amber-500' },
  contested:           { icon: <Swords className="h-3.5 w-3.5" />,      label: 'Contested',           color: 'text-red-500' },
  proposed:            { icon: <Lightbulb className="h-3.5 w-3.5" />,   label: 'Proposed',            color: 'text-blue-500' },
  next:                { icon: <ArrowRight className="h-3.5 w-3.5" />,  label: 'Next',                color: 'text-gray-500' },
}

const OUTCOME_COLORS: Record<string, string> = {
  confirmed: 'border-green-500',
  below_target: 'border-amber-500',
  inconclusive: 'border-gray-400',
  rejected: 'border-red-500',
}

const OUTCOME_BADGES: Record<string, { label: string; cls: string }> = {
  confirmed: { label: 'Confirmed', cls: 'bg-green-500/10 text-green-600' },
  below_target: { label: 'Below target', cls: 'bg-amber-500/10 text-amber-600' },
  inconclusive: { label: 'Inconclusive', cls: 'bg-gray-500/10 text-gray-500' },
  rejected: { label: 'Rejected', cls: 'bg-red-500/10 text-red-600' },
}

function scoreColor(score: number | null): string {
  if (score === null) return 'text-muted-foreground'
  if (score >= 0.85) return 'text-green-500'
  if (score >= 0.70) return 'text-amber-500'
  return 'text-red-500'
}

function journeyHeader(status: LabStateStatus): string {
  if (status === 'established') return 'Research Journey'
  if (status === 'under_investigation') return 'Progress so far'
  if (status === 'contested') return 'Debate timeline'
  if (status === 'proposed') return 'Proposal details'
  return 'Next steps'
}

function AuditTrail({ chain }: { chain: SignatureEntry[] }) {
  const [open, setOpen] = useState(false)

  return (
    <div className="mt-2">
      <button
        onClick={() => setOpen(!open)}
        className="text-[10px] text-muted-foreground hover:text-foreground transition-colors flex items-center gap-1"
      >
        <Shield className="h-3 w-3" />
        {open ? 'Hide' : 'Show'} verified audit trail ({chain.length} entries)
      </button>
      {open && (
        <div className="mt-1.5 space-y-0.5 font-mono text-[10px] text-muted-foreground">
          {chain.map((entry, i) => (
            <div key={i} className="flex gap-2">
              <span className="w-20 shrink-0">{new Date(entry.timestamp).toLocaleDateString()}</span>
              <span className="w-32 shrink-0">{entry.action}</span>
              <span className="text-muted-foreground/60 truncate">{entry.signature_hash}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function EvidenceTimeline({ evidence }: { evidence: EvidenceEntry[] }) {
  return (
    <div className="space-y-1">
      {evidence.map((ev, i) => {
        const borderColor = ev.outcome ? OUTCOME_COLORS[ev.outcome] ?? 'border-gray-300' : 'border-gray-300'
        const isWaiting = ev.description.startsWith('Waiting:')

        return (
          <div key={i} className={`flex items-start gap-2 text-xs border-l-2 pl-2 py-0.5 ${borderColor}`}>
            {ev.dayLabel && (
              <span className="w-12 shrink-0 text-[10px] text-muted-foreground/70">{ev.dayLabel}</span>
            )}
            <span className="inline-flex items-center rounded bg-muted px-1.5 py-0.5 text-[10px] font-medium capitalize shrink-0">
              {ev.type}
            </span>
            <span className={`flex-1 ${isWaiting ? 'text-amber-600' : 'text-muted-foreground'}`}>
              {ev.description}
            </span>
            <span className="text-[10px] italic text-muted-foreground/70 shrink-0">{ev.agent}</span>
            {ev.outcome && OUTCOME_BADGES[ev.outcome] && (
              <span className={`inline-flex items-center rounded-full px-1.5 py-0.5 text-[9px] font-medium shrink-0 ${OUTCOME_BADGES[ev.outcome].cls}`}>
                {OUTCOME_BADGES[ev.outcome].label}
              </span>
            )}
          </div>
        )
      })}
    </div>
  )
}

interface LabStatePanelProps {
  slug: string
  highlightItemId?: string | null
  items?: LabStateItem[]
}

export function LabStatePanel({ slug, highlightItemId, items: externalItems }: LabStatePanelProps) {
  const [collapsed, setCollapsed] = useState(false)
  const [expandedItem, setExpandedItem] = useState<string | null>(null)
  const [highlightActive, setHighlightActive] = useState<string | null>(null)
  const itemRefs = useRef<Map<string, HTMLDivElement>>(new Map())

  const items: LabStateItem[] = externalItems ?? MOCK_LAB_STATE[slug] ?? []

  // Highlight behavior: auto-expand and scroll to target item
  useEffect(() => {
    if (!highlightItemId) return

    setCollapsed(false)
    setExpandedItem(highlightItemId)
    setHighlightActive(highlightItemId)

    // Scroll into view after a tick (to allow DOM to expand)
    requestAnimationFrame(() => {
      const el = itemRefs.current.get(highlightItemId)
      if (el) {
        el.scrollIntoView({ behavior: 'smooth', block: 'center' })
      }
    })

    const timer = setTimeout(() => setHighlightActive(null), 1500)
    return () => clearTimeout(timer)
  }, [highlightItemId])

  if (items.length === 0) return null

  return (
    <div className="rounded-lg border bg-card">
      {/* Header */}
      <button
        onClick={() => setCollapsed(!collapsed)}
        className="flex items-center gap-2 w-full p-3 text-left hover:bg-muted/30 transition-colors"
      >
        {collapsed ? <ChevronRight className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
        <span className="text-sm font-medium">Lab State</span>
        <span className="text-xs text-muted-foreground ml-auto">{items.length} items</span>
      </button>

      {/* Items */}
      {!collapsed && (
        <div className="border-t divide-y">
          {items.map(item => {
            const statusCfg = STATUS_CONFIG[item.status]
            const domainStyle = getDomainStyle(item.domain)
            const isExpanded = expandedItem === item.id
            const isHighlighted = highlightActive === item.id
            const domainProfile = DOMAIN_PROFILES[item.domain]

            return (
              <div
                key={item.id}
                ref={el => { if (el) itemRefs.current.set(item.id, el) }}
                className={`px-3 py-2 transition-all ${isHighlighted ? 'ring-2 ring-primary ring-offset-1 rounded' : ''}`}
              >
                {/* Collapsed row */}
                <button
                  onClick={() => setExpandedItem(isExpanded ? null : item.id)}
                  className="flex items-center gap-3 w-full text-left"
                >
                  <span className={statusCfg.color}>{statusCfg.icon}</span>
                  <div className="flex-1 min-w-0">
                    <span className="text-sm font-medium truncate block">{item.title}</span>
                    {item.currentSummary && !isExpanded && (
                      <span className="text-xs text-muted-foreground/70 truncate block">{item.currentSummary}</span>
                    )}
                  </div>
                  {item.verificationScore !== null && (
                    <span className={`text-xs font-mono font-medium ${scoreColor(item.verificationScore)}`}>
                      {(item.verificationScore * 100).toFixed(0)}%
                    </span>
                  )}
                  <span className="text-xs text-muted-foreground">{item.referenceCount} refs</span>
                  <span className={`inline-flex items-center rounded-full px-1.5 py-0.5 text-[10px] font-medium ${domainStyle.bg} ${domainStyle.text}`}>
                    {item.domain.replace(/_/g, ' ')}
                  </span>
                </button>

                {/* Expanded view */}
                {isExpanded && (
                  <div className="mt-3 ml-7 space-y-3">
                    {/* Domain verification info */}
                    {domainProfile && (
                      <p className="text-[10px] italic text-muted-foreground/60">{domainProfile.summary}</p>
                    )}

                    {/* Current summary */}
                    {item.currentSummary && (
                      <p className="text-xs text-muted-foreground">{item.currentSummary}</p>
                    )}

                    {/* Research journey */}
                    {item.evidence.length > 0 && (
                      <>
                        <h4 className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wide">
                          {journeyHeader(item.status)}
                        </h4>
                        <EvidenceTimeline evidence={item.evidence} />
                      </>
                    )}

                    {item.evidence.length === 0 && (
                      <p className="text-xs text-muted-foreground italic">No evidence yet</p>
                    )}

                    {/* Audit trail for established items */}
                    {item.status === 'established' && item.signatureChain && item.signatureChain.length > 0 && (
                      <AuditTrail chain={item.signatureChain} />
                    )}
                  </div>
                )}
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
