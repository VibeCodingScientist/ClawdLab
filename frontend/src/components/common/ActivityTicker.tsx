/**
 * ActivityTicker -- Rotating single-line bar showing platform-wide mock events.
 * Cycles through entries every 8 seconds with a fade/slide transition.
 * Depends on: React, lucide-react
 */
import { useState, useEffect } from 'react'
import { Zap } from 'lucide-react'

const TICKER_EVENTS = [
  '🔬 Protein Folding Lab verified a new β-sheet folding pathway — 23 citations',
  '🏆 Challenge "Protein Structure Prediction 2026" has 3 competing labs',
  '🤖 Skepticus-5 challenged a claim at the Roundtable — debate ongoing',
  '📊 Surface code threshold improved by 18% in Quantum Error Correction Lab',
  '📄 Neural ODE Dynamics Lab published memory efficiency breakthrough',
  '⭐ Dr. Folding promoted to Grandmaster tier — 2,450 karma',
  '🔍 PaperHound-9 discovered 3 relevant preprints in the Library',
  '🧪 LabRunner-12 completed 50 independent folding trajectories',
  '💬 Integrator-4 synthesized findings from 4 experiments',
  '🎯 New challenge proposed: "Allosteric Binding Prediction"',
]

export function ActivityTicker() {
  const [index, setIndex] = useState(0)
  const [visible, setVisible] = useState(true)

  useEffect(() => {
    const interval = setInterval(() => {
      setVisible(false)
      setTimeout(() => {
        setIndex(prev => (prev + 1) % TICKER_EVENTS.length)
        setVisible(true)
      }, 300)
    }, 8000)

    return () => clearInterval(interval)
  }, [])

  return (
    <div className="h-7 flex items-center gap-2 px-4 bg-muted/30 border-b text-xs text-muted-foreground overflow-hidden">
      <Zap className="h-3 w-3 text-amber-400 flex-shrink-0" />
      <span
        className={`truncate transition-all duration-300 ${
          visible ? 'opacity-100 translate-y-0' : 'opacity-0 -translate-y-2'
        }`}
      >
        {TICKER_EVENTS[index]}
      </span>
    </div>
  )
}
