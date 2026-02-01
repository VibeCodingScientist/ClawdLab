export function isMockMode(): boolean {
  return import.meta.env.VITE_MOCK_MODE === 'true'
}

export const MOCK_DELAY_MS = 300
