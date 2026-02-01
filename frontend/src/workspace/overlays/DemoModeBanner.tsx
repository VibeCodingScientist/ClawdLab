/**
 * DemoModeBanner -- React banner indicating the app is running in demo/mock mode.
 * Depends on: isMockMode, lucide-react
 */
import { isMockMode } from '@/mock/useMockMode'
import { Sparkles } from 'lucide-react'

export function DemoModeBanner() {
  if (!isMockMode()) return null

  return (
    <div className="bg-amber-500/10 border border-amber-500/20 rounded-lg px-4 py-2 flex items-center gap-2">
      <Sparkles className="h-4 w-4 text-amber-500" />
      <span className="text-sm text-amber-500 font-medium">
        Demo Mode — Using simulated data. Agents move and interact autonomously.
      </span>
    </div>
  )
}
