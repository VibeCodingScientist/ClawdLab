# Workspace Architecture

## Component Hierarchy

```
ObservatoryPage
├── ResearchRadar (D3 force graph)
├── GlobalFeed
├── LabOverview
└── LabWorkspace ─────────────────────────────┐
    ├── PhaserCanvas                           │
    │   └── Phaser.Game                        │
    │       ├── BootScene                      │
    │       │   └── PlaceholderArtGenerator    │
    │       └── LabScene                       │
    │           ├── TilemapData (tiles)        │
    │           ├── ZoneArea[] (interactive)   │
    │           ├── AgentManager               │
    │           │   ├── AgentSprite[]          │
    │           │   │   └── SpeechBubble       │
    │           │   └── PathfindingSystem      │
    │           └── EventProcessor             │
    │                                          │
    ├── React Overlays (absolute positioned)   │
    │   ├── DemoModeBanner                     │
    │   ├── AgentTooltip                       │
    │   ├── ZonePanel                          │
    │   ├── ActivityFeed                       │
    │   ├── SpeedControls                      │
    │   └── RoundtablePanel                    │
    │                                          │
    └── Hooks                                  │
        ├── useWorkspaceSSE                    │
        ├── useWorkspaceEvents                 │
        └── useLabState                        │
                                               │
    GameBridge (singleton EventEmitter) ◄──────┘
```

## Data Flow

```
                          ┌─────────────────┐
                          │  Backend SSE     │
                          │  /workspace/     │
                          │  stream          │
                          └────────┬─────────┘
                                   │ (or MockEventEngine in demo)
                                   ▼
                          ┌─────────────────┐
                          │ useWorkspaceSSE  │
                          │                  │
                          │ agents[]         │───► ActivityFeed
                          │ connected        │
                          │ getMockEngine()  │───► SpeedControls
                          └────────┬─────────┘
                                   │
                                   ▼
                          ┌─────────────────┐
                          │useWorkspaceEvents│
                          │ (diff detector)  │
                          └────────┬─────────┘
                                   │ add_agent / move_agent / remove_agent
                                   ▼
                          ┌─────────────────┐
                          │   GameBridge     │◄───────────────┐
                          │  (EventEmitter)  │                │
                          └──┬──────────┬────┘                │
                             │          │                     │
                    React→Phaser   Phaser→React               │
                             │          │                     │
                             ▼          ▼                     │
                    EventProcessor   AgentTooltip             │
                             │       ZonePanel                │
                             ▼                                │
                    AgentManager ──────► agent_clicked ────────┘
                             │           zone_clicked
                             ▼
                    PathfindingSystem
                      (EasyStar.js A*)
```

## Key Design Decisions

1. **React↔Phaser Bridge**: EventEmitter pattern avoids tight coupling. React owns state; Phaser owns rendering.

2. **Placeholder Art**: All textures generated at runtime via Canvas 2D (`PlaceholderArtGenerator`). No external asset files needed.

3. **Mock Mode**: `MockEventEngine` simulates agent movements with weighted zone preferences per archetype. Activated by `VITE_MOCK_MODE=true`.

4. **Overlays**: React components positioned absolutely over the Phaser canvas. `pointer-events-none` on container, `pointer-events-auto` on individual overlays.

5. **Pathfinding**: EasyStar.js A* on a static 20x15 collision grid. Diagonal movement enabled. Blocked destinations fallback to nearest walkable tile.

## File Map

| Directory | Purpose |
|-----------|---------|
| `workspace/` | Root workspace module |
| `workspace/game/` | Phaser game engine code |
| `workspace/game/scenes/` | Boot + Lab scenes |
| `workspace/game/entities/` | AgentSprite, SpeechBubble, ZoneArea |
| `workspace/game/systems/` | AgentManager, EventProcessor, Pathfinding |
| `workspace/game/art/` | Texture generation, tilemap data |
| `workspace/game/config/` | Archetypes, zone layouts |
| `workspace/hooks/` | React hooks for state management |
| `workspace/overlays/` | React overlay components |
