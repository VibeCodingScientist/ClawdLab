/**
 * useLabStateData -- React hook for fetching and caching lab state items + active objective via react-query.
 * Depends on: @tanstack/react-query, getLabState & getLabStates API
 */
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { getLabState, getLabStates } from '@/api/workspace'

export function useLabStateData(slug: string) {
  const queryClient = useQueryClient()

  const itemsQuery = useQuery({
    queryKey: ['lab-state-items', slug],
    queryFn: () => getLabState(slug),
    enabled: !!slug,
    staleTime: 30_000,
  })

  const objectiveQuery = useQuery({
    queryKey: ['lab-state-objective', slug],
    queryFn: () =>
      getLabStates(slug).then(
        states => states.find(s => s.status === 'active') ?? null,
      ),
    enabled: !!slug,
    staleTime: 60_000,
  })

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ['lab-state-items', slug] })
    queryClient.invalidateQueries({ queryKey: ['lab-state-objective', slug] })
  }

  return {
    labStateItems: itemsQuery.data ?? [],
    activeObjective: objectiveQuery.data ?? null,
    isLoading: itemsQuery.isLoading,
    error: itemsQuery.error,
    invalidate,
  }
}
