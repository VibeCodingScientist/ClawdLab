/**
 * useLabState -- React hook that fetches lab detail, members, stats, and research items.
 * Depends on: @tanstack/react-query, workspace API client
 */
import { useQuery } from '@tanstack/react-query'
import {
  getLabDetail,
  getLabMembers,
  getLabStats,
  getLabResearch,
} from '@/api/workspace'

export function useLabState(slug: string) {
  const detail = useQuery({
    queryKey: ['lab-detail', slug],
    queryFn: () => getLabDetail(slug),
    enabled: !!slug,
  })

  const members = useQuery({
    queryKey: ['lab-members', slug],
    queryFn: () => getLabMembers(slug),
    enabled: !!slug,
  })

  const stats = useQuery({
    queryKey: ['lab-stats', slug],
    queryFn: () => getLabStats(slug),
    enabled: !!slug,
  })

  const research = useQuery({
    queryKey: ['lab-research', slug],
    queryFn: () => getLabResearch(slug),
    enabled: !!slug,
  })

  return {
    detail: detail.data,
    members: members.data,
    stats: stats.data,
    research: research.data,
    isLoading: detail.isLoading || members.isLoading || stats.isLoading || research.isLoading,
    error: detail.error || members.error || stats.error || research.error,
  }
}
