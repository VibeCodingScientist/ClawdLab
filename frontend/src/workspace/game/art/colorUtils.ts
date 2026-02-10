/**
 * colorUtils -- Shared color helper functions extracted from PlaceholderArtGenerator.
 * No external dependencies.
 */

export function hexToRgb(hex: string): { r: number; g: number; b: number } {
  const result = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex)
  return result
    ? { r: parseInt(result[1], 16), g: parseInt(result[2], 16), b: parseInt(result[3], 16) }
    : { r: 128, g: 128, b: 128 }
}

export function rgbToHex(r: number, g: number, b: number): string {
  const toHex = (v: number) => Math.max(0, Math.min(255, Math.round(v))).toString(16).padStart(2, '0')
  return `#${toHex(r)}${toHex(g)}${toHex(b)}`
}

export function darken(hex: string, amount = 0.3): string {
  const { r, g, b } = hexToRgb(hex)
  return rgbToHex(r * (1 - amount), g * (1 - amount), b * (1 - amount))
}

export function lighten(hex: string, amount = 0.3): string {
  const { r, g, b } = hexToRgb(hex)
  return rgbToHex(r + (255 - r) * amount, g + (255 - g) * amount, b + (255 - b) * amount)
}

/** Set a single pixel on a canvas context */
export function px(ctx: CanvasRenderingContext2D, x: number, y: number, color: string): void {
  ctx.fillStyle = color
  ctx.fillRect(x, y, 1, 1)
}

/** Draw a horizontal line */
export function hline(ctx: CanvasRenderingContext2D, x: number, y: number, w: number, color: string): void {
  ctx.fillStyle = color
  ctx.fillRect(x, y, w, 1)
}

/** Draw a vertical line */
export function vline(ctx: CanvasRenderingContext2D, x: number, y: number, h: number, color: string): void {
  ctx.fillStyle = color
  ctx.fillRect(x, y, 1, h)
}
