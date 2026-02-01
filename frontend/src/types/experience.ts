/**
 * experience types -- Re-exports from API client plus frontend-specific types.
 * No external dependencies beyond the API module.
 */
export type {
  ExperienceResponse,
  DomainXPDetail,
  MilestoneResponse,
  LeaderboardEntry,
} from '@/api/experience'

export type LeaderboardTab = 'global' | 'domain' | 'deployers'

export interface LeaderboardFilter {
  tab: LeaderboardTab
  domain?: string
  limit: number
}
