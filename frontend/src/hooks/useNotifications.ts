/**
 * React Query hook for notifications — polling, fetching, and mutations.
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useAuth } from '@/hooks/useAuth'
import {
  fetchNotifications,
  fetchUnreadCount,
  markNotificationRead,
  markAllNotificationsRead,
} from '@/api/notifications'

const UNREAD_POLL_MS = 30_000

export function useNotifications() {
  const { user } = useAuth()
  const queryClient = useQueryClient()
  const isAuthenticated = !!user

  const unreadCountQuery = useQuery({
    queryKey: ['notifications', 'unread-count'],
    queryFn: fetchUnreadCount,
    enabled: isAuthenticated,
    refetchInterval: UNREAD_POLL_MS,
    staleTime: 10_000,
  })

  const notificationsQuery = useQuery({
    queryKey: ['notifications', 'list'],
    queryFn: () => fetchNotifications(),
    enabled: false, // only fetch on demand (when popover opens)
  })

  const markReadMutation = useMutation({
    mutationFn: markNotificationRead,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['notifications'] })
    },
  })

  const markAllReadMutation = useMutation({
    mutationFn: markAllNotificationsRead,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['notifications'] })
    },
  })

  return {
    unreadCount: unreadCountQuery.data?.unreadCount ?? 0,
    notifications: notificationsQuery.data?.items ?? [],
    isLoading: notificationsQuery.isLoading,
    isFetching: notificationsQuery.isFetching,
    refetchNotifications: notificationsQuery.refetch,
    markRead: markReadMutation.mutate,
    markAllRead: markAllReadMutation.mutate,
  }
}
