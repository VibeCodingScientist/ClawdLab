/**
 * Notification bell popover — shows unread count badge and notification list.
 */

import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Bell,
  FlaskConical,
  MessageSquare,
  MessageCircle,
  TrendingUp,
  CheckCircle,
} from 'lucide-react'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/common/Popover'
import { Button } from '@/components/common/Button'
import { useNotifications } from '@/hooks/useNotifications'
import type { Notification, NotificationType } from '@/types'

const TYPE_ICONS: Record<NotificationType, typeof Bell> = {
  lab_created_from_post: FlaskConical,
  comment_reply: MessageSquare,
  post_comment: MessageCircle,
  agent_level_up: TrendingUp,
  task_completed: CheckCircle,
}

function relativeTime(dateStr: string): string {
  const diff = Date.now() - new Date(dateStr).getTime()
  const minutes = Math.floor(diff / 60000)
  if (minutes < 1) return 'just now'
  if (minutes < 60) return `${minutes}m ago`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.floor(hours / 24)
  return `${days}d ago`
}

export function NotificationPopover() {
  const [open, setOpen] = useState(false)
  const navigate = useNavigate()
  const {
    unreadCount,
    notifications,
    isFetching,
    refetchNotifications,
    markRead,
    markAllRead,
  } = useNotifications()

  const handleOpenChange = (isOpen: boolean) => {
    setOpen(isOpen)
    if (isOpen) {
      refetchNotifications()
    }
  }

  const handleClick = (notif: Notification) => {
    if (!notif.readAt) {
      markRead(notif.id)
    }
    if (notif.link) {
      navigate(notif.link)
      setOpen(false)
    }
  }

  const handleMarkAllRead = () => {
    markAllRead()
  }

  return (
    <Popover open={open} onOpenChange={handleOpenChange}>
      <PopoverTrigger asChild>
        <Button variant="ghost" size="icon" className="relative">
          <Bell className="h-5 w-5" />
          {unreadCount > 0 && (
            <span className="absolute right-1 top-1 h-2 w-2 rounded-full bg-destructive" />
          )}
        </Button>
      </PopoverTrigger>
      <PopoverContent align="end" className="w-[380px] max-h-[480px] p-0">
        {/* Header */}
        <div className="flex items-center justify-between border-b px-4 py-3">
          <h3 className="text-sm font-semibold">Notifications</h3>
          {unreadCount > 0 && (
            <button
              onClick={handleMarkAllRead}
              className="text-xs text-muted-foreground hover:text-foreground transition-colors"
            >
              Mark all read
            </button>
          )}
        </div>

        {/* List */}
        <div className="overflow-y-auto max-h-[420px]">
          {isFetching && notifications.length === 0 ? (
            <div className="flex items-center justify-center py-8 text-sm text-muted-foreground">
              Loading...
            </div>
          ) : notifications.length === 0 ? (
            <div className="flex items-center justify-center py-8 text-sm text-muted-foreground">
              No notifications yet
            </div>
          ) : (
            notifications.map((notif) => {
              const Icon = TYPE_ICONS[notif.notificationType] || Bell
              const isUnread = !notif.readAt
              return (
                <button
                  key={notif.id}
                  onClick={() => handleClick(notif)}
                  className={`flex w-full items-start gap-3 px-4 py-3 text-left transition-colors hover:bg-accent/50 ${
                    isUnread ? 'bg-accent/20' : ''
                  }`}
                >
                  <Icon className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" />
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-medium leading-tight">{notif.title}</p>
                    <p className="mt-0.5 text-xs text-muted-foreground line-clamp-2">
                      {notif.body}
                    </p>
                    <p className="mt-1 text-xs text-muted-foreground/60">
                      {relativeTime(notif.createdAt)}
                    </p>
                  </div>
                  {isUnread && (
                    <span className="mt-2 h-2 w-2 shrink-0 rounded-full bg-primary" />
                  )}
                </button>
              )
            })
          )}
        </div>
      </PopoverContent>
    </Popover>
  )
}
