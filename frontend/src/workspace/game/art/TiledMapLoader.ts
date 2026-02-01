/**
 * TiledMapLoader -- Loads Tiled JSON map data from disk or falls back to hardcoded TILE_LAYER.
 * Depends on: Phaser, TILE_LAYER from TilemapData
 */

import Phaser from 'phaser'
import { TILE_LAYER } from './TilemapData'

interface TiledLayer {
  data: number[]
  width: number
  height: number
  name: string
  type: string
}

interface TiledMap {
  width: number
  height: number
  layers: TiledLayer[]
  tilewidth: number
  tileheight: number
}

export class TiledMapLoader {
  /**
   * Attempt to load a Tiled JSON map. Falls back to hardcoded TILE_LAYER on failure.
   *
   * Tries to fetch `/assets/maps/lab-map.json`, parses the Tiled JSON format,
   * and converts the flat tile data array into a 2D grid. Tiled uses 1-based
   * tile IDs, so each value is decremented by 1 for our 0-based tileset frames.
   *
   * @param _scene - The Phaser scene (reserved for future cache-based loading)
   * @returns A 2D number array representing the tile grid
   */
  static async load(_scene: Phaser.Scene): Promise<number[][]> {
    try {
      const response = await fetch('/assets/maps/lab-map.json')
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`)
      }

      const json: TiledMap = await response.json()
      const groundLayer = json.layers.find(l => l.type === 'tilelayer') ?? json.layers[0]

      if (!groundLayer || !groundLayer.data) {
        throw new Error('No valid tile layer found in Tiled JSON')
      }

      // Convert flat array to 2D grid
      const grid: number[][] = []
      const width = groundLayer.width || json.width
      const height = groundLayer.height || json.height

      for (let y = 0; y < height; y++) {
        const row: number[] = []
        for (let x = 0; x < width; x++) {
          // Tiled uses 1-based tile IDs; subtract 1 for our 0-based tileset frames
          const rawId = groundLayer.data[y * width + x] ?? 0
          row.push(Math.max(0, rawId - 1))
        }
        grid.push(row)
      }

      console.log(`[TiledMapLoader] Loaded Tiled map (${width}x${height}) from /assets/maps/lab-map.json`)
      return grid
    } catch (err) {
      console.log('[TiledMapLoader] Tiled map not available, using hardcoded TILE_LAYER:', (err as Error).message)
      return TILE_LAYER
    }
  }
}
