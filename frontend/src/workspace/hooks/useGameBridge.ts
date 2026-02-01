import { useRef } from 'react'
import { GameBridge, type GameBridgeType } from '../game/GameBridge'

export function useGameBridge(): GameBridgeType {
  const bridgeRef = useRef<GameBridgeType>(GameBridge.getInstance())
  return bridgeRef.current
}
