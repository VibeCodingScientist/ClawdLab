/**
 * SpeedControls -- React overlay providing pause/1x/2x/5x speed controls for the mock event engine.
 * Depends on: GameBridge, MockEventEngine
 */
import { Pause, Play, FastForward } from 'lucide-react'
import { Button } from '@/components/common/Button'
import { GameBridge } from '../game/GameBridge'

interface SpeedControlsProps {
  getMockEngine: () => import('@/mock/mockEventEngine').MockEventEngine | null
  speed: number
  onSpeedChange: (speed: number) => void
}

const SPEEDS = [
  { label: 'Pause', value: 0, icon: Pause },
  { label: '1x', value: 1, icon: Play },
  { label: '2x', value: 2, icon: FastForward },
  { label: '5x', value: 5, icon: FastForward },
]

export function SpeedControls({ getMockEngine, speed, onSpeedChange }: SpeedControlsProps) {
  const handleSpeed = (value: number) => {
    onSpeedChange(value)
    getMockEngine()?.setSpeed(value)
    GameBridge.getInstance().emit('set_speed', value)
  }

  return (
    <div className="absolute bottom-3 right-3 z-30 flex items-center gap-1 bg-card/90 backdrop-blur border rounded-lg p-1 shadow-lg">
      {SPEEDS.map(s => {
        const Icon = s.icon
        const isActive = speed === s.value
        return (
          <Button
            key={s.value}
            variant={isActive ? 'default' : 'ghost'}
            size="sm"
            onClick={() => handleSpeed(s.value)}
            className="h-7 px-2 text-xs"
            title={s.label}
          >
            <Icon className="h-3 w-3 mr-1" />
            {s.label}
          </Button>
        )
      })}
    </div>
  )
}
