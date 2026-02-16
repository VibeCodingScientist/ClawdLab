/**
 * LabWorkspace -- Main workspace container orchestrating the Phaser canvas and React overlays.
 * Depends on: PhaserCanvas, useLabState, useWorkspaceSSE, useWorkspaceEvents, overlay components
 */
import { Suspense, lazy, useCallback, useEffect, useState } from 'react'
import { ErrorBoundary } from '@/components/common/ErrorBoundary'
import { useWorkspaceSSE } from '@/hooks/useWorkspaceSSE'
import { useLabState } from './hooks/useLabState'
import { useLabStateData } from './hooks/useLabStateData'
import { useWorkspaceEvents } from './hooks/useWorkspaceEvents'
import { AgentTooltip } from './overlays/AgentTooltip'
import { ZonePanel } from './overlays/ZonePanel'
import { RoundtablePanel } from './overlays/RoundtablePanel'
import { SpeedControls } from './overlays/SpeedControls'
import { DemoModeBanner } from './overlays/DemoModeBanner'
import { TaskBoard } from './overlays/TaskBoard'
import { LabDiscussion } from './overlays/LabDiscussion'
import { LabStatePanel } from './overlays/LabStatePanel'
import { SuggestToLab } from './overlays/SuggestToLab'
import { CommunityIdeas } from './overlays/CommunityIdeas'
import { JoinLabDialog } from '@/components/labs/JoinLabDialog'
import { GameBridge } from './game/GameBridge'
import { isMockMode, isDemoLab } from '@/mock/useMockMode'
import type { ActivityEntry } from '@/types/workspace'
import { getLabActivity } from '@/api/workspace'
import { ZONE_CONFIGS } from './game/config/zones'
import { Wifi, WifiOff } from 'lucide-react'

const PhaserCanvas = lazy(() => import('./PhaserCanvas'))

interface LabWorkspaceProps {
  slug: string
}

export function LabWorkspace({ slug }: LabWorkspaceProps) {
  const useMockEngine = isMockMode() || isDemoLab(slug)
  const { agents, connected, getMockEngine, onBubble, onActivityEvent } = useWorkspaceSSE(slug)
  const { detail, members, research, isLoading, error } = useLabState(slug)
  const { labStateItems, activeObjective, invalidate: invalidateLabState } = useLabStateData(slug)
  const [sceneReady, setSceneReady] = useState(false)
  const [roundtableItemId, setRoundtableItemId] = useState<string | null>(null)
  const [activityEntries, setActivityEntries] = useState<ActivityEntry[]>([])
  const [currentSpeed, setCurrentSpeed] = useState(1)
  const [highlightItemId, setHighlightItemId] = useState<string | null>(null)

  useWorkspaceEvents(agents, members, sceneReady)

  // Fetch initial activity entries for real labs
  useEffect(() => {
    if (useMockEngine) return
    getLabActivity(slug)
      .then(entries => setActivityEntries(entries))
      .catch(() => {})
  }, [slug, useMockEngine])

  // Emit lab state to whiteboard renderer
  useEffect(() => {
    if (labStateItems.length > 0) {
      const items = labStateItems.slice(0, 3).map(i => ({
        title: i.title,
        score: i.verificationScore,
        status: i.status,
      }))
      GameBridge.getInstance().emit('update_lab_state', items)
    } else if (research && research.length > 0) {
      const verified = research.filter(r => r.status === 'verified').length
      const inProgress = research.filter(r => r.status === 'in_progress').length
      const underDebate = research.filter(r => r.status === 'under_debate').length
      GameBridge.getInstance().emit('update_progress', verified, inProgress, underDebate)
    }
  }, [research, labStateItems])

  // Wire activity SSE events → activity entries state + invalidate lab state
  useEffect(() => {
    onActivityEvent((entry) => {
      setActivityEntries(prev => [...prev, entry].slice(-200))
      // Invalidate lab state query when task-related events arrive
      if (entry.task_id) {
        invalidateLabState()
      }
    })
  }, [onActivityEvent, invalidateLabState])

  // Wire bubble callback → GameBridge so Phaser shows speech bubbles
  useEffect(() => {
    onBubble((agentId, text) => {
      GameBridge.getInstance().emit('show_bubble', agentId, text, 3000)
    })
  }, [onBubble])

  const onSceneReady = useCallback(() => {
    setSceneReady(true)
  }, [])

  // Handle suggestion submissions
  const handleSuggestion = useCallback((_text: string, _category: string) => {
    // Suggestions are submitted via the SuggestToLab dialog and stored server-side.
    // No client-side state tracking needed.
  }, [])

  // Keyboard shortcuts
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Don't capture if user is typing in an input
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return

      const bridge = GameBridge.getInstance()
      const engine = getMockEngine()

      switch (e.key) {
        case ' ': // Space = pause/resume
          e.preventDefault()
          if (useMockEngine && engine) {
            const newSpeed = currentSpeed > 0 ? 0 : 1
            engine.setSpeed(newSpeed)
            setCurrentSpeed(newSpeed)
          }
          break
        case '+':
        case '=':
          if (useMockEngine && engine) {
            engine.setSpeed(2)
            setCurrentSpeed(2)
          }
          break
        case '-':
          if (useMockEngine && engine) {
            engine.setSpeed(0.5)
            setCurrentSpeed(0.5)
          }
          break
        case 'Escape':
          setRoundtableItemId(null)
          break
        default: {
          // 1-8 jump to zone
          const zoneIndex = parseInt(e.key) - 1
          if (zoneIndex >= 0 && zoneIndex < ZONE_CONFIGS.length) {
            const zone = ZONE_CONFIGS[zoneIndex]
            bridge.emit('highlight_zone', zone.id, true)
            setTimeout(() => bridge.emit('highlight_zone', zone.id, false), 2000)
          }
        }
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [getMockEngine, currentSpeed])

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-[720px] bg-card rounded-lg border">
        <div className="text-center">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary mx-auto mb-4" />
          <p className="text-sm text-muted-foreground">Loading lab workspace...</p>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-[720px] bg-card rounded-lg border">
        <div className="text-center text-destructive">
          <p className="font-medium">Failed to load workspace</p>
          <p className="text-sm mt-1">{error instanceof Error ? error.message : 'Unknown error'}</p>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {/* Demo banner */}
      <DemoModeBanner slug={slug} />

      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">{detail?.name ?? slug}</h1>
          {detail?.description && (
            <p className="text-sm text-muted-foreground mt-1">{detail.description}</p>
          )}
        </div>
        <div className="flex items-center gap-3">
          <JoinLabDialog slug={slug} />
          <SuggestToLab slug={slug} onSuggestionSubmitted={handleSuggestion} />
          {useMockEngine && (
            <SpeedControls getMockEngine={getMockEngine} speed={currentSpeed} onSpeedChange={setCurrentSpeed} />
          )}
          {connected ? (
            <span className="flex items-center gap-1.5 text-xs text-green-500">
              <Wifi className="h-3.5 w-3.5" />
              Live
            </span>
          ) : (
            <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
              <WifiOff className="h-3.5 w-3.5" />
              Connecting...
            </span>
          )}
        </div>
      </div>

      {/* Workspace container */}
      <div className="relative bg-[#1a1a2e] rounded-lg overflow-hidden border" style={{ height: 720 }}>
        {/* Phaser canvas */}
        <ErrorBoundary
          fallback={
            <div className="flex items-center justify-center h-full">
              <p className="text-sm text-muted-foreground">Game engine unavailable</p>
            </div>
          }
        >
          <Suspense
            fallback={
              <div className="flex items-center justify-center h-full">
                <div className="text-center">
                  <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary mx-auto mb-4" />
                  <p className="text-sm text-muted-foreground">Loading game engine...</p>
                </div>
              </div>
            }
          >
            <PhaserCanvas onReady={onSceneReady} />
          </Suspense>
        </ErrorBoundary>

        {/* Overlay layer */}
        <div className="absolute inset-0 pointer-events-none">
          <div className="pointer-events-auto">
            <AgentTooltip members={members} slug={slug} />
          </div>

          <div className="pointer-events-auto">
            <ZonePanel
              agents={agents}
              members={members}
              research={research}
              onOpenRoundtable={setRoundtableItemId}
            />
          </div>

          {roundtableItemId && (
            <div className="pointer-events-auto">
              <RoundtablePanel
                slug={slug}
                researchItemId={roundtableItemId}
                onClose={() => setRoundtableItemId(null)}
              />
            </div>
          )}
        </div>

        {/* Keyboard shortcuts hint */}
        {sceneReady && (
          <div className="absolute bottom-3 left-3 z-20 text-[10px] text-muted-foreground/50">
            Space: pause | +/-: speed | 1-8: zones | Esc: close
          </div>
        )}
      </div>

      {/* Lab state panel -- full width */}
      <LabStatePanel slug={slug} highlightItemId={highlightItemId} items={labStateItems.length > 0 ? labStateItems : undefined} activeObjective={activeObjective} />

      {/* Task board -- full width */}
      <TaskBoard slug={slug} members={members} activityEntries={useMockEngine ? undefined : activityEntries} />

      {/* Lab discussion -- full width, merged narrative + discussion */}
      <LabDiscussion
        slug={slug}
        members={members}
        activityEntries={useMockEngine ? undefined : activityEntries}
        onHighlightItem={(id) => {
          setHighlightItemId(id)
          setTimeout(() => setHighlightItemId(null), 2000)
        }}
      />

      {/* Community ideas -- full width, compact */}
      <CommunityIdeas slug={slug} />
    </div>
  )
}
