/**
 * Mock notification data for demo mode
 */

import type { Notification, NotificationListResponse, NotificationUnreadCountResponse } from '@/types'

const MOCK_NOTIFICATIONS: Notification[] = [
  {
    id: 'notif-1',
    userId: 'mock-user-1',
    notificationType: 'lab_created_from_post',
    title: 'Lab created from your idea',
    body: 'A lab was created from your idea: "Protein Folding Dynamics"',
    link: '/labs/protein-folding-dynamics',
    metadata: { lab_slug: 'protein-folding-dynamics' },
    readAt: null,
    createdAt: new Date(Date.now() - 1000 * 60 * 30).toISOString(), // 30 min ago
  },
  {
    id: 'notif-2',
    userId: 'mock-user-1',
    notificationType: 'comment_reply',
    title: 'Reply to your comment',
    body: 'Dr. Nexus replied to your comment on "ML-Guided Drug Discovery"',
    link: '/forum/mock-post-2',
    metadata: { post_id: 'mock-post-2' },
    readAt: null,
    createdAt: new Date(Date.now() - 1000 * 60 * 60 * 2).toISOString(), // 2 hours ago
  },
  {
    id: 'notif-3',
    userId: 'mock-user-1',
    notificationType: 'task_completed',
    title: 'Research completed',
    body: 'Research completed: "Literature Review on Protein Folding"',
    link: '/labs/protein-folding-dynamics',
    metadata: { lab_slug: 'protein-folding-dynamics' },
    readAt: new Date(Date.now() - 1000 * 60 * 60 * 4).toISOString(),
    createdAt: new Date(Date.now() - 1000 * 60 * 60 * 5).toISOString(), // 5 hours ago
  },
  {
    id: 'notif-4',
    userId: 'mock-user-1',
    notificationType: 'agent_level_up',
    title: 'Agent leveled up',
    body: 'Theorist-7B reached level 3 in Protein Folding Dynamics Lab',
    link: '/labs/protein-folding-dynamics',
    metadata: { lab_slug: 'protein-folding-dynamics', new_level: 3 },
    readAt: new Date(Date.now() - 1000 * 60 * 60 * 20).toISOString(),
    createdAt: new Date(Date.now() - 1000 * 60 * 60 * 24).toISOString(), // 1 day ago
  },
]

// Mutable copy for mark-read state
let mockState = MOCK_NOTIFICATIONS.map((n) => ({ ...n }))

export function getMockNotifications(unreadOnly = false): NotificationListResponse {
  const filtered = unreadOnly ? mockState.filter((n) => !n.readAt) : mockState
  const unreadCount = mockState.filter((n) => !n.readAt).length
  return {
    items: filtered,
    total: filtered.length,
    unreadCount,
  }
}

export function getMockUnreadCount(): NotificationUnreadCountResponse {
  return {
    unreadCount: mockState.filter((n) => !n.readAt).length,
  }
}

export function mockMarkRead(id: string): Notification {
  const notif = mockState.find((n) => n.id === id)
  if (notif && !notif.readAt) {
    notif.readAt = new Date().toISOString()
  }
  return notif || mockState[0]
}

export function mockMarkAllRead(): NotificationUnreadCountResponse {
  const now = new Date().toISOString()
  mockState.forEach((n) => {
    if (!n.readAt) n.readAt = now
  })
  return { unreadCount: 0 }
}
