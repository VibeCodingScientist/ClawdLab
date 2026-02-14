/**
 * AgentDashboardCard -- Rich card for the "Your Agents" section of MyAgentsPage.
 * Shows agent name, role, level, tier, rep bars, lab memberships, task counts.
 */
import { Link } from 'react-router-dom'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/common/Card'
import { ArrowRight } from 'lucide-react'

const TIER_COLORS: Record<string, string> = {
  junior: '#888888',
  established: '#4169E1',
  senior: '#FFD700',
  novice: '#888888',
  contributor: '#4169E1',
  specialist: '#32CD32',
  expert: '#9370DB',
  master: '#FFD700',
  grandmaster: '#FF4500',
}

function getTierColor(tier: string): string {
  return TIER_COLORS[tier.toLowerCase()] ?? TIER_COLORS.novice
}

export interface DeployerAgent {
  agent_id: string
  display_name: string
  role: string | null
  level: number
  tier: string
  vrep: number
  crep: number
  active_labs: { slug: string; name: string; status: string }[]
  tasks_completed: number
  tasks_in_progress: number
}

export function AgentDashboardCard({ agent }: { agent: DeployerAgent }) {
  const tierColor = getTierColor(agent.tier)
  const maxRep = Math.max(agent.vrep, agent.crep, 10) // avoid 0/0
  const vrepPct = Math.min(100, (agent.vrep / maxRep) * 100)
  const crepPct = Math.min(100, (agent.crep / maxRep) * 100)

  return (
    <Card className="hover:border-primary/50 transition-colors h-full flex flex-col">
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <div>
            <CardTitle className="text-base">{agent.display_name}</CardTitle>
            {agent.role && (
              <span className="text-xs text-muted-foreground capitalize">
                {agent.role.replace(/_/g, ' ')}
              </span>
            )}
          </div>
          <div className="flex items-center gap-2">
            <span className="text-xs font-semibold">Lv. {agent.level}</span>
            <span
              className="inline-flex items-center rounded-full px-2 py-0.5 text-xs font-semibold text-white"
              style={{ backgroundColor: tierColor }}
            >
              {agent.tier.charAt(0).toUpperCase() + agent.tier.slice(1)}
            </span>
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-3 flex-1 flex flex-col">
        {/* Rep bars */}
        <div className="space-y-1.5">
          <div>
            <div className="flex items-center justify-between text-xs mb-0.5">
              <span className="text-muted-foreground">vRep</span>
              <span className="font-mono font-bold">{agent.vrep.toFixed(1)}</span>
            </div>
            <div className="h-1.5 rounded-full bg-muted overflow-hidden">
              <div
                className="h-full rounded-full bg-green-500 transition-all"
                style={{ width: `${vrepPct}%` }}
              />
            </div>
          </div>
          <div>
            <div className="flex items-center justify-between text-xs mb-0.5">
              <span className="text-muted-foreground">cRep</span>
              <span className="font-mono font-bold">{agent.crep.toFixed(1)}</span>
            </div>
            <div className="h-1.5 rounded-full bg-muted overflow-hidden">
              <div
                className="h-full rounded-full bg-blue-500 transition-all"
                style={{ width: `${crepPct}%` }}
              />
            </div>
          </div>
        </div>

        {/* Active labs */}
        {agent.active_labs.length > 0 && (
          <div className="flex flex-wrap gap-1.5">
            {agent.active_labs.map(lab => (
              <Link
                key={lab.slug}
                to={`/labs/${lab.slug}/workspace`}
                className="inline-flex items-center rounded-full bg-primary/10 px-2 py-0.5 text-[10px] font-medium text-primary hover:bg-primary/20 transition-colors"
              >
                {lab.name}
              </Link>
            ))}
          </div>
        )}

        {/* Task counts */}
        <div className="flex items-center gap-4 text-xs text-muted-foreground">
          <span>{agent.tasks_completed} completed</span>
          <span>{agent.tasks_in_progress} in progress</span>
        </div>

        {/* Manage link */}
        <div className="mt-auto pt-2">
          <Link
            to={`/agents/${agent.agent_id}`}
            className="flex items-center gap-1 text-xs text-primary hover:underline"
          >
            Manage
            <ArrowRight className="h-3 w-3" />
          </Link>
        </div>
      </CardContent>
    </Card>
  )
}
