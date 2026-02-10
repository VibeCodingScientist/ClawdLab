/**
 * TilemapData -- Static 20x15 tilemap layout and collision grid for the lab scene.
 * No external dependencies.
 */
// 20x15 tile grid
// Tile indices:
// 0 = floor, 1 = wall, 2 = bookshelf, 3 = lab bench,
// 4 = terminal, 5 = whiteboard, 6 = round table, 7 = chair,
// 8 = coffee machine, 9 = door, 10 = display, 11 = verification machine,
// 12 = command desk, 13 = papers, 14 = zone border, 15 = empty

// Base tile layer
export const TILE_LAYER: number[][] = [
  // y=0:  PI Desk        | Ideation       | Library             | Whiteboard
  [1,  1,  1,  1,  1,   1,  1,  1,  1,  1,   1,  1,  1,  1,  1,   1,  1,  1,  1,  1],
  [1, 12, 13,  0,  0,   0,  0,  7,  0,  0,   0,  2,  2,  2,  0,   0,  0,  5,  5,  1],
  [1,  0,  0,  0,  7,   0,  0,  0,  0,  0,   0,  0,  0,  0,  0,   0,  0,  0,  0,  1],
  [1,  0,  0,  0,  0,   0,  0,  0,  0,  0,   0,  0, 13,  0,  0,   0,  0,  0, 13,  1],
  // y=4-8: Lab Bench                       | Library cont.       | Whiteboard cont.
  [1,  0,  0,  0,  0,   0,  0,  0,  0,  0,   0,  2,  0,  2,  0,   0,  0,  0,  0,  1],
  [1,  3,  0,  3,  0,   0,  3,  0,  3,  0,   0,  0,  0,  0,  0,   0,  4,  0,  4,  1],
  [1,  0,  0,  0,  0,   4,  0,  0,  0,  0,   0,  0,  0,  0,  0,   0,  0,  0,  0,  1],
  [1,  3,  0, 11,  0,   0,  3,  0,  0,  0,   0,  0,  0,  0,  0,   0,  0, 10,  0,  1],
  [1,  0,  0,  0,  0,   0,  0,  0,  0,  0,   0,  0,  0,  0,  0,   0,  0,  0,  0,  1],
  // y=9-14: Entrance/Break  | Roundtable              | Presentation
  [1,  0,  0,  0,  0,  0,   0,  0,  0,  0,  0,  0,  0,  0,   0,  0,  0,  0,  0,  1],
  [1,  0,  8,  0,  0,  0,   0,  0,  0,  0,  0,  0,  0,  0,   0,  0, 10,  0,  0,  1],
  [1,  0,  0,  0,  7,  0,   0,  7,  0,  6,  6,  6,  0,  7,   0,  0,  0,  0,  0,  1],
  [1,  0,  0,  0,  0,  0,   0,  0,  6,  6,  6,  6,  6,  0,   0,  0,  0, 10,  0,  1],
  [1,  9,  0,  0,  7,  0,   0,  7,  0,  6,  6,  6,  0,  7,   0,  0,  0,  0,  0,  1],
  [1,  1,  1,  1,  1,  1,   1,  1,  1,  1,  1,  1,  1,  1,   1,  1,  1,  1,  1,  1],
]

// Collision grid: true = blocked
export const COLLISION_GRID: boolean[][] = TILE_LAYER.map(row =>
  row.map(tile => {
    // Walls, furniture, equipment = blocked
    const blocked = [1, 2, 3, 5, 6, 8, 10, 11, 12]
    return blocked.includes(tile)
  })
)

// Zone overlay indices (for coloring zones on the map)
// 0 = no zone highlight, 1-8 = zone IDs matching ZONE_CONFIGS order
export const ZONE_OVERLAY: number[][] = [
  [0, 1, 1, 1, 1,  2, 2, 2, 2, 0,  3, 3, 3, 3, 3,  4, 4, 4, 4, 0],
  [0, 1, 1, 1, 1,  2, 2, 2, 2, 0,  3, 3, 3, 3, 3,  0, 4, 4, 4, 0],
  [0, 1, 1, 1, 1,  2, 2, 2, 2, 2,  3, 3, 3, 3, 3,  4, 4, 4, 4, 0],
  [0, 1, 1, 1, 1,  2, 2, 2, 2, 0,  3, 3, 3, 3, 3,  0, 4, 4, 4, 0],
  [0, 5, 5, 5, 5,  5, 5, 5, 5, 0,  3, 3, 3, 3, 3,  4, 4, 4, 4, 0],
  [0, 5, 5, 5, 5,  5, 5, 5, 5, 5,  3, 3, 3, 3, 3,  4, 4, 4, 4, 0],
  [0, 5, 5, 5, 5,  5, 5, 5, 5, 0,  3, 3, 3, 3, 3,  4, 4, 4, 4, 0],
  [0, 5, 5, 5, 5,  5, 5, 5, 5, 5,  0, 0, 0, 0, 0,  0, 7, 7, 7, 0],
  [0, 5, 5, 5, 5,  5, 5, 5, 5, 0,  0, 0, 0, 0, 7,  7, 7, 7, 7, 0],
  [0, 8, 8, 8, 8,  8, 0, 6, 6, 6,  6, 6, 6, 6, 0,  7, 7, 7, 7, 0],
  [0, 8, 8, 8, 8,  8, 6, 6, 6, 6,  6, 6, 6, 6, 7,  7, 7, 7, 7, 0],
  [0, 8, 8, 8, 8,  8, 6, 6, 6, 6,  6, 6, 6, 6, 7,  7, 7, 7, 7, 0],
  [0, 8, 8, 8, 8,  8, 6, 6, 6, 6,  6, 6, 6, 6, 7,  7, 7, 7, 7, 0],
  [0, 8, 8, 8, 8,  8, 6, 6, 6, 6,  6, 6, 6, 6, 7,  7, 7, 7, 7, 0],
  [0, 0, 0, 0, 0,  0, 0, 0, 0, 0,  0, 0, 0, 0, 0,  0, 0, 0, 0, 0],
]

// Tile type names for the art generator
export const TILE_NAMES: string[] = [
  'floor',              // 0
  'wall',               // 1
  'bookshelf',          // 2
  'lab_bench',          // 3
  'terminal',           // 4
  'whiteboard',         // 5
  'round_table',        // 6
  'chair',              // 7
  'coffee_machine',     // 8
  'door',               // 9
  'display',            // 10
  'verification_machine', // 11
  'command_desk',       // 12
  'papers',             // 13
  'zone_border',        // 14
  'empty',              // 15
]
