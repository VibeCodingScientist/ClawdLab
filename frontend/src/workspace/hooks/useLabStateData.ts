/**
 * useLabStateData -- React hook for fetching and caching lab state items via react-query.
 * Depends on: @tanstack/react-query, getLabState API
 */
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { getLabState } from '@/api/workspace'

export function useLabStateData(slug: string) {
  const queryClient = useQueryClient()

  const { data, isLoading, error } = useQuery({
    queryKey: ['lab-state-items', slug],
    queryFn: () => getLabState(slug),
    enabled: !!slug,
    staleTime: 30_000,
  })

  const invalidate = () =>
    queryClient.invalidateQueries({ queryKey: ['lab-state-items', slug] })

  return { labStateItems: data ?? [], isLoading, error, invalidate }
}
