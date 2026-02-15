/**
 * DemoModeBanner -- React banner indicating the workspace uses simulated agent activity.
 * Shows for mock mode or demo labs in production.
 */
import { isMockMode, isDemoLab } from '@/mock/useMockMode'
import { Sparkles } from 'lucide-react'

export function DemoModeBanner({ slug }: { slug?: string }) {
  if (!isMockMode() && !(slug && isDemoLab(slug))) return null

  return (
    <div className="bg-amber-500/10 border border-amber-500/20 rounded-lg px-4 py-2 flex items-center gap-2">
      <Sparkles className="h-4 w-4 text-amber-500" />
      <span className="text-sm text-amber-500 font-medium">
        Demo — Simulated agent activity. Agents move and interact autonomously.
      </span>
    </div>
  )
}
