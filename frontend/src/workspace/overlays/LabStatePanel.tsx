/**
 * LabStatePanel -- Collapsible full-width panel showing structured research state.
 * Displays lab state items with status icons, verification scores, and expandable evidence.
 * Depends on: LabStateItem type, MOCK_LAB_STATE, lucide-react, getDomainStyle
 */
import { useState } from 'react'
import { ChevronDown, ChevronRight, CheckCircle, Search, Swords, Lightbulb, ArrowRight } from 'lucide-react'
import type { LabStateItem, LabStateStatus } from '@/types/workspace'
import { MOCK_LAB_STATE } from '@/mock/mockData'
import { getDomainStyle } from '@/utils/domainStyles'

const STATUS_CONFIG: Record<LabStateStatus, { icon: React.ReactNode; label: string; color: string }> = {
  established:         { icon: <CheckCircle className="h-3.5 w-3.5" />, label: 'Established',         color: 'text-green-500' },
  under_investigation: { icon: <Search className="h-3.5 w-3.5" />,      label: 'Under Investigation', color: 'text-amber-500' },
  contested:           { icon: <Swords className="h-3.5 w-3.5" />,      label: 'Contested',           color: 'text-red-500' },
  proposed:            { icon: <Lightbulb className="h-3.5 w-3.5" />,   label: 'Proposed',            color: 'text-blue-500' },
  next:                { icon: <ArrowRight className="h-3.5 w-3.5" />,  label: 'Next',                color: 'text-gray-500' },
}

function scoreColor(score: number | null): string {
  if (score === null) return 'text-muted-foreground'
  if (score >= 0.85) return 'text-green-500'
  if (score >= 0.70) return 'text-amber-500'
  return 'text-red-500'
}

interface LabStatePanelProps {
  slug: string
}

export function LabStatePanel({ slug }: LabStatePanelProps) {
  const [collapsed, setCollapsed] = useState(false)
  const [expandedItem, setExpandedItem] = useState<string | null>(null)

  const items: LabStateItem[] = MOCK_LAB_STATE[slug] ?? []

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

            return (
              <div key={item.id} className="px-3 py-2">
                <button
                  onClick={() => setExpandedItem(isExpanded ? null : item.id)}
                  className="flex items-center gap-3 w-full text-left"
                >
                  <span className={statusCfg.color}>{statusCfg.icon}</span>
                  <span className="text-sm font-medium flex-1 truncate">{item.title}</span>
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

                {/* Expanded evidence */}
                {isExpanded && item.evidence.length > 0 && (
                  <div className="mt-2 ml-7 space-y-1.5">
                    {item.evidence.map((ev, i) => (
                      <div key={i} className="flex items-start gap-2 text-xs text-muted-foreground">
                        <span className="inline-flex items-center rounded bg-muted px-1.5 py-0.5 text-[10px] font-medium capitalize">
                          {ev.type}
                        </span>
                        <span className="flex-1">{ev.description}</span>
                        <span className="text-[10px] italic">{ev.agent}</span>
                      </div>
                    ))}
                  </div>
                )}

                {isExpanded && item.evidence.length === 0 && (
                  <p className="mt-2 ml-7 text-xs text-muted-foreground italic">No evidence yet</p>
                )}
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
