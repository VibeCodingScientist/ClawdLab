export function isMockMode(): boolean {
  return import.meta.env.VITE_MOCK_MODE === 'true'
}

/** Demo lab slugs that use mock workspace data even in production. */
const DEMO_LAB_SLUGS = new Set(['protein-folding-dynamics'])

export function isDemoLab(slug: string): boolean {
  return DEMO_LAB_SLUGS.has(slug)
}

export const MOCK_DELAY_MS = 300
