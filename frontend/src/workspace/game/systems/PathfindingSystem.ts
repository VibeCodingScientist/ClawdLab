/**
 * PathfindingSystem -- A* pathfinding on the collision grid using EasyStar.js.
 * Depends on: easystarjs, COLLISION_GRID, MAP_WIDTH/MAP_HEIGHT
 */
import EasyStar from 'easystarjs'
import { COLLISION_GRID } from '../art/TilemapData'
import { MAP_WIDTH, MAP_HEIGHT } from '../config/zones'

interface PathPoint {
  x: number
  y: number
}

export class PathfindingSystem {
  private easystar: EasyStar.js

  constructor() {
    this.easystar = new EasyStar.js()

    // Build grid: 0 = walkable, 1 = blocked
    const grid: number[][] = []
    for (let y = 0; y < MAP_HEIGHT; y++) {
      const row: number[] = []
      for (let x = 0; x < MAP_WIDTH; x++) {
        row.push(COLLISION_GRID[y]?.[x] ? 1 : 0)
      }
      grid.push(row)
    }

    this.easystar.setGrid(grid)
    this.easystar.setAcceptableTiles([0])
    this.easystar.enableDiagonals()
    this.easystar.setIterationsPerCalculation(100)
  }

  findPath(startX: number, startY: number, endX: number, endY: number): Promise<PathPoint[]> {
    // Clamp to grid bounds
    const sx = Math.max(0, Math.min(MAP_WIDTH - 1, Math.round(startX)))
    const sy = Math.max(0, Math.min(MAP_HEIGHT - 1, Math.round(startY)))
    let ex = Math.max(0, Math.min(MAP_WIDTH - 1, Math.round(endX)))
    let ey = Math.max(0, Math.min(MAP_HEIGHT - 1, Math.round(endY)))

    // If destination is blocked, find nearest walkable tile
    if (COLLISION_GRID[ey]?.[ex]) {
      const nearest = this.findNearestWalkable(ex, ey)
      if (nearest) {
        ex = nearest.x
        ey = nearest.y
      }
    }

    return new Promise((resolve, reject) => {
      this.easystar.findPath(sx, sy, ex, ey, (path) => {
        if (path === null) {
          reject(new Error(`No path from (${sx},${sy}) to (${ex},${ey})`))
        } else {
          resolve(path)
        }
      })
      this.easystar.calculate()
    })
  }

  private findNearestWalkable(x: number, y: number): PathPoint | null {
    for (let radius = 1; radius <= 5; radius++) {
      for (let dy = -radius; dy <= radius; dy++) {
        for (let dx = -radius; dx <= radius; dx++) {
          const nx = x + dx
          const ny = y + dy
          if (nx >= 0 && nx < MAP_WIDTH && ny >= 0 && ny < MAP_HEIGHT) {
            if (!COLLISION_GRID[ny]?.[nx]) {
              return { x: nx, y: ny }
            }
          }
        }
      }
    }
    return null
  }
}
