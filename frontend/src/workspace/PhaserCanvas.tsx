/**
 * PhaserCanvas -- Mounts and manages a Phaser 3 game instance inside a React component.
 * Depends on: Phaser, LabGameConfig, GameBridge
 */
import { useEffect, useRef } from 'react'
import Phaser from 'phaser'
import { createLabGameConfig } from './game/LabGameConfig'
import { GameBridge } from './game/GameBridge'

interface PhaserCanvasProps {
  onReady?: () => void
}

export default function PhaserCanvas({ onReady }: PhaserCanvasProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const gameRef = useRef<Phaser.Game | null>(null)
  const onReadyRef = useRef(onReady)
  onReadyRef.current = onReady

  useEffect(() => {
    if (gameRef.current) return // Prevent React strict mode double-mount
    if (!containerRef.current) return

    const config = createLabGameConfig(containerRef.current)
    const game = new Phaser.Game(config)
    gameRef.current = game

    const bridge = GameBridge.getInstance()
    const handleReady = () => {
      onReadyRef.current?.()
    }
    bridge.on('scene_ready', handleReady)

    return () => {
      bridge.off('scene_ready', handleReady)
      GameBridge.destroy()
      game.destroy(true)
      gameRef.current = null
    }
  }, [])

  return (
    <div
      ref={containerRef}
      className="w-full h-full"
      style={{ imageRendering: 'pixelated' }}
    />
  )
}
