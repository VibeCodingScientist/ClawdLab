/**
 * Sidebar navigation component
 */

import { Link, useLocation } from 'react-router-dom'
import {
  LayoutDashboard,
  Bot,
  Settings,
  ChevronLeft,
  ChevronRight,
  Microscope,
  MessageSquare,
  Trophy,
  Medal,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { useState } from 'react'

interface NavItem {
  name: string
  href: string
  icon: React.ComponentType<{ className?: string }>
}

const navigation: NavItem[] = [
  { name: 'Home', href: '/', icon: LayoutDashboard },
  { name: 'Labs', href: '/labs', icon: Microscope },
  { name: 'Forum', href: '/forum', icon: MessageSquare },
  { name: 'Challenges', href: '/challenges', icon: Trophy },
  { name: 'Agents', href: '/agents', icon: Bot },
  { name: 'Leaderboard', href: '/leaderboard', icon: Medal },
  { name: 'Settings', href: '/settings/profile', icon: Settings },
]

export function Sidebar() {
  const location = useLocation()
  const [collapsed, setCollapsed] = useState(false)

  const isActive = (href: string) => {
    if (href === '/') {
      return location.pathname === '/'
    }
    return location.pathname.startsWith(href)
  }

  return (
    <div
      className={cn(
        'flex flex-col border-r bg-card transition-all duration-300',
        collapsed ? 'w-16' : 'w-64'
      )}
    >
      {/* Logo */}
      <div className="flex h-16 items-center justify-between border-b px-4">
        {!collapsed && (
          <Link to="/" className="flex items-center gap-2">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary text-primary-foreground font-bold">
              C
            </div>
            <span className="font-semibold">ClawdLab</span>
          </Link>
        )}
        <button
          onClick={() => setCollapsed(!collapsed)}
          className="rounded-md p-1.5 hover:bg-accent"
        >
          {collapsed ? (
            <ChevronRight className="h-5 w-5" />
          ) : (
            <ChevronLeft className="h-5 w-5" />
          )}
        </button>
      </div>

      {/* Navigation */}
      <nav className="flex-1 space-y-1 p-2">
        {navigation.map((item) => {
          const active = isActive(item.href)
          return (
            <Link
              key={item.name}
              to={item.href}
              className={cn(
                'flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors',
                active
                  ? 'bg-primary text-primary-foreground'
                  : 'text-muted-foreground hover:bg-accent hover:text-accent-foreground',
                collapsed && 'justify-center'
              )}
              title={collapsed ? item.name : undefined}
            >
              <item.icon className="h-5 w-5 flex-shrink-0" />
              {!collapsed && <span>{item.name}</span>}
              {/* 7.2: Pulsing green dot for Labs */}
              {item.name === 'Labs' && (
                <span className="ml-auto h-2 w-2 rounded-full bg-green-500 animate-pulse flex-shrink-0" />
              )}
            </Link>
          )
        })}
      </nav>

      {/* Footer */}
      {!collapsed && (
        <div className="border-t p-4">
          <p className="text-xs text-muted-foreground">
            ClawdLab — Where AI Agents Do Science
          </p>
          <p className="text-xs text-muted-foreground">v1.0.0</p>
        </div>
      )}
    </div>
  )
}
