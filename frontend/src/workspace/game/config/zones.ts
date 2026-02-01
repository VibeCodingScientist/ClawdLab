/**
 * zones -- Zone layout configuration: positions, spawn points, tile/scale constants.
 * Depends on: WorkspaceZone type
 */
import type { WorkspaceZone } from '@/types/workspace'

export interface ZoneConfig {
  id: string
  backendZone: WorkspaceZone
  label: string
  tileRect: { x: number; y: number; w: number; h: number }
  centerTile: { x: number; y: number }
  color: string
  spawnPoints: { x: number; y: number }[]
}

// 20x15 tile grid, 16px tiles at 3x scale = 960x720
export const ZONE_CONFIGS: ZoneConfig[] = [
  {
    id: 'pi-desk',
    backendZone: 'ideation',
    label: 'PI Desk',
    tileRect: { x: 0, y: 0, w: 5, h: 4 },
    centerTile: { x: 2, y: 2 },
    color: '#FFD700',
    spawnPoints: [{ x: 1, y: 1 }, { x: 3, y: 2 }, { x: 2, y: 3 }],
  },
  {
    id: 'ideation',
    backendZone: 'ideation',
    label: 'Ideation Corner',
    tileRect: { x: 5, y: 0, w: 5, h: 4 },
    centerTile: { x: 7, y: 2 },
    color: '#FFA500',
    spawnPoints: [{ x: 6, y: 1 }, { x: 8, y: 2 }, { x: 7, y: 3 }],
  },
  {
    id: 'library',
    backendZone: 'library',
    label: 'Library',
    tileRect: { x: 10, y: 0, w: 5, h: 7 },
    centerTile: { x: 12, y: 3 },
    color: '#4169E1',
    spawnPoints: [{ x: 11, y: 1 }, { x: 13, y: 2 }, { x: 12, y: 4 }, { x: 11, y: 5 }],
  },
  {
    id: 'whiteboard',
    backendZone: 'whiteboard',
    label: 'Whiteboard',
    tileRect: { x: 15, y: 0, w: 5, h: 7 },
    centerTile: { x: 17, y: 3 },
    color: '#9370DB',
    spawnPoints: [{ x: 16, y: 1 }, { x: 18, y: 2 }, { x: 17, y: 5 }],
  },
  {
    id: 'bench',
    backendZone: 'bench',
    label: 'Lab Bench',
    tileRect: { x: 0, y: 4, w: 10, h: 5 },
    centerTile: { x: 5, y: 6 },
    color: '#32CD32',
    spawnPoints: [{ x: 1, y: 5 }, { x: 3, y: 6 }, { x: 5, y: 7 }, { x: 7, y: 5 }, { x: 9, y: 6 }],
  },
  {
    id: 'roundtable',
    backendZone: 'roundtable',
    label: 'Roundtable',
    tileRect: { x: 6, y: 9, w: 8, h: 6 },
    centerTile: { x: 10, y: 12 },
    color: '#FF6347',
    spawnPoints: [{ x: 7, y: 10 }, { x: 9, y: 11 }, { x: 11, y: 10 }, { x: 13, y: 11 }, { x: 10, y: 13 }],
  },
  {
    id: 'presentation',
    backendZone: 'presentation',
    label: 'Presentation',
    tileRect: { x: 14, y: 7, w: 6, h: 8 },
    centerTile: { x: 17, y: 11 },
    color: '#00CED1',
    spawnPoints: [{ x: 15, y: 8 }, { x: 17, y: 9 }, { x: 19, y: 10 }, { x: 16, y: 12 }],
  },
  {
    id: 'entrance',
    backendZone: 'ideation',
    label: 'Entrance',
    tileRect: { x: 0, y: 9, w: 6, h: 6 },
    centerTile: { x: 3, y: 12 },
    color: '#8B4513',
    spawnPoints: [{ x: 1, y: 10 }, { x: 3, y: 11 }, { x: 5, y: 13 }],
  },
]

export function getZoneByBackendZone(backendZone: WorkspaceZone): ZoneConfig {
  // Several zones can map to the same backend zone (e.g. 'pi-desk', 'ideation', 'entrance'
  // all map to backend zone 'ideation'). Prefer the zone whose ID matches exactly, so
  // agents sent to 'ideation' land in the Ideation Corner, not the PI Desk.
  const exact = ZONE_CONFIGS.find(z => z.id === backendZone)
  if (exact) return exact
  return ZONE_CONFIGS.find(z => z.backendZone === backendZone) ?? ZONE_CONFIGS[0]
}

export function getZoneById(id: string): ZoneConfig | undefined {
  return ZONE_CONFIGS.find(z => z.id === id)
}

export const TILE_SIZE = 16
export const SCALE = 3
export const MAP_WIDTH = 20
export const MAP_HEIGHT = 15
export const CANVAS_WIDTH = MAP_WIDTH * TILE_SIZE * SCALE   // 960
export const CANVAS_HEIGHT = MAP_HEIGHT * TILE_SIZE * SCALE  // 720
