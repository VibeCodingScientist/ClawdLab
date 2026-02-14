/**
 * monitoring mock handler -- Mock data for system health status.
 */
import type { SystemStatus } from '@/types'
import { MOCK_DELAY_MS } from '../useMockMode'

function delay<T>(data: T): Promise<T> {
  return new Promise(resolve => setTimeout(() => resolve(data), MOCK_DELAY_MS))
}

const MOCK_SYSTEM_STATUS: SystemStatus = {
  status: 'healthy',
  checks: {
    database: { status: 'healthy', latencyMs: 2 },
    redis: { status: 'healthy', latencyMs: 1 },
    api: { status: 'healthy', latencyMs: 12 },
    scheduler: { status: 'healthy', message: 'Running' },
  },
  timestamp: new Date().toISOString(),
}

export function mockGetSystemHealth(): Promise<SystemStatus> {
  return delay({ ...MOCK_SYSTEM_STATUS, timestamp: new Date().toISOString() })
}
