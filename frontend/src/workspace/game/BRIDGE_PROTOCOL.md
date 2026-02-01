# GameBridge Protocol

The `GameBridge` is an EventEmitter singleton (`GameBridge.ts`) that enables bidirectional communication between the React overlay layer and the Phaser 3 game engine.

## Event Reference

### React → Phaser

| Event | Payload | Description |
|-------|---------|-------------|
| `add_agent` | `(agent: WorkspaceAgentExtended)` | Spawn a new agent sprite in the scene |
| `move_agent` | `(agentId, zone, x, y)` | Pathfind agent to a new zone/position |
| `remove_agent` | `(agentId: string)` | Destroy agent sprite |
| `show_bubble` | `(agentId, text, duration)` | Display speech bubble above agent |
| `update_agent_status` | `(agentId, status)` | Update agent status label |
| `set_speed` | `(multiplier: number)` | Adjust game tick speed |
| `highlight_zone` | `(zoneId, active: boolean)` | Toggle zone highlight overlay |

### Phaser → React

| Event | Payload | Description |
|-------|---------|-------------|
| `agent_clicked` | `(agentId: string)` | User clicked an agent sprite |
| `agent_hovered` | `(agentId, screenX, screenY)` | Mouse entered agent hitbox |
| `agent_unhovered` | `()` | Mouse left agent hitbox |
| `zone_clicked` | `(zoneId: string)` | User clicked a zone area |
| `scene_ready` | `()` | LabScene finished initialization |

## Data Flow

```
  useWorkspaceSSE (SSE / MockEventEngine)
        │
        ▼
  useWorkspaceEvents (diff detection)
        │
        ▼
    GameBridge ──────────────────┐
        │                        │
   React → Phaser           Phaser → React
        │                        │
        ▼                        ▼
  EventProcessor            React Overlays
        │                  (AgentTooltip,
        ▼                   ZonePanel, etc.)
  AgentManager
        │
        ▼
  AgentSprite / PathfindingSystem
```

## Usage

```typescript
// React side
const bridge = GameBridge.getInstance()
bridge.emit('add_agent', agentData)
bridge.on('agent_clicked', (id) => { /* show detail */ })

// Phaser side (in LabScene)
this.bridge.on('highlight_zone', (zoneId, active) => { ... })
this.bridge.emit('scene_ready')
```

## Lifecycle

1. `BootScene` generates textures and animations
2. `LabScene.create()` builds tilemap, zones, wires bridge listeners
3. `LabScene` emits `scene_ready` → React sets `sceneReady=true`
4. `useWorkspaceEvents` emits `add_agent` for each SSE agent
5. User interactions flow back via `agent_clicked`, `zone_clicked`
6. On unmount, `LabScene.shutdown()` removes all bridge listeners
