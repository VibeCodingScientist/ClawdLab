/**
 * Notification API client
 */

import apiClient from '@/api/client'
import { isMockMode, MOCK_DELAY_MS } from '@/mock/useMockMode'
import { getMockNotifications, getMockUnreadCount, mockMarkRead, mockMarkAllRead } from '@/mock/handlers/notifications'
import type { Notification, NotificationListResponse, NotificationUnreadCountResponse } from '@/types'

function mapNotification(raw: Record<string, unknown>): Notification {
  return {
    id: raw.id as string,
    userId: (raw.user_id ?? raw.userId) as string,
    notificationType: (raw.notification_type ?? raw.notificationType) as Notification['notificationType'],
    title: raw.title as string,
    body: raw.body as string,
    link: (raw.link ?? null) as string | null,
    metadata: (raw.metadata ?? {}) as Record<string, unknown>,
    readAt: (raw.read_at ?? raw.readAt ?? null) as string | null,
    createdAt: (raw.created_at ?? raw.createdAt) as string,
  }
}

export async function fetchNotifications(unreadOnly = false): Promise<NotificationListResponse> {
  if (isMockMode()) {
    await new Promise((r) => setTimeout(r, MOCK_DELAY_MS))
    return getMockNotifications(unreadOnly)
  }
  const params: Record<string, string | boolean> = {}
  if (unreadOnly) params.unread_only = true
  const res = await apiClient.get('/notifications', { params })
  const data = res.data
  return {
    items: (data.items || []).map(mapNotification),
    total: data.total ?? 0,
    unreadCount: data.unread_count ?? data.unreadCount ?? 0,
  }
}

export async function fetchUnreadCount(): Promise<NotificationUnreadCountResponse> {
  if (isMockMode()) {
    await new Promise((r) => setTimeout(r, MOCK_DELAY_MS))
    return getMockUnreadCount()
  }
  const res = await apiClient.get('/notifications/unread-count')
  return {
    unreadCount: res.data.unread_count ?? res.data.unreadCount ?? 0,
  }
}

export async function markNotificationRead(id: string): Promise<Notification> {
  if (isMockMode()) {
    await new Promise((r) => setTimeout(r, MOCK_DELAY_MS))
    return mockMarkRead(id)
  }
  const res = await apiClient.post(`/notifications/${id}/read`)
  return mapNotification(res.data)
}

export async function markAllNotificationsRead(): Promise<NotificationUnreadCountResponse> {
  if (isMockMode()) {
    await new Promise((r) => setTimeout(r, MOCK_DELAY_MS))
    return mockMarkAllRead()
  }
  const res = await apiClient.post('/notifications/read-all')
  return {
    unreadCount: res.data.unread_count ?? res.data.unreadCount ?? 0,
  }
}
