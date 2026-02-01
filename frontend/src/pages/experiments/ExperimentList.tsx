/**
 * Experiment list page -- Shows example experiment cards from mock data.
 */

import { Link } from 'react-router-dom'
import { FlaskConical, Plus, Clock, CheckCircle, Play } from 'lucide-react'
import { Button } from '@/components/common/Button'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/common/Card'
import { MOCK_EXPERIMENTS } from '@/mock/mockData'

const STATUS_CONFIG: Record<string, { icon: React.ReactNode; bg: string; text: string; label: string }> = {
  completed: {
    icon: <CheckCircle className="h-3.5 w-3.5" />,
    bg: 'bg-green-900/30',
    text: 'text-green-400',
    label: 'Completed',
  },
  running: {
    icon: <Play className="h-3.5 w-3.5" />,
    bg: 'bg-amber-900/30',
    text: 'text-amber-400',
    label: 'Running',
  },
  pending: {
    icon: <Clock className="h-3.5 w-3.5" />,
    bg: 'bg-gray-900/30',
    text: 'text-gray-400',
    label: 'Pending',
  },
  failed: {
    icon: <FlaskConical className="h-3.5 w-3.5" />,
    bg: 'bg-red-900/30',
    text: 'text-red-400',
    label: 'Failed',
  },
}

export default function ExperimentList() {
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Experiments</h1>
          <p className="text-muted-foreground">
            Design, schedule, and monitor experiments
          </p>
        </div>
        <Link to="/experiments/new">
          <Button>
            <Plus className="mr-2 h-4 w-4" />
            New Experiment
          </Button>
        </Link>
      </div>

      {/* Explainer */}
      <Card className="bg-muted/30 border-dashed">
        <CardContent className="py-4">
          <div className="flex items-start gap-3">
            <FlaskConical className="h-5 w-5 text-primary mt-0.5" />
            <div>
              <p className="text-sm font-medium">What are Experiments?</p>
              <p className="text-sm text-muted-foreground mt-1">
                Experiments are structured computational tasks that lab agents design and execute to test hypotheses.
                Each experiment has defined parameters, metrics, and reproducibility requirements.
                Results are automatically verified and feed back into the lab's research pipeline.
              </p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Experiment cards */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {MOCK_EXPERIMENTS.map(exp => {
          const statusConfig = STATUS_CONFIG[exp.status] ?? STATUS_CONFIG.pending

          return (
            <Card key={exp.id} className="hover:border-primary/50 transition-colors">
              <CardHeader className="pb-2">
                <div className="flex items-center justify-between">
                  <span className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium ${statusConfig.bg} ${statusConfig.text}`}>
                    {statusConfig.icon}
                    {statusConfig.label}
                  </span>
                  <span className="inline-flex items-center rounded-full bg-muted px-2 py-0.5 text-[10px] font-medium text-muted-foreground">
                    Example
                  </span>
                </div>
                <CardTitle className="text-base mt-2">{exp.name}</CardTitle>
                <CardDescription className="text-xs line-clamp-2">
                  {exp.description}
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-2">
                <div className="flex flex-wrap gap-1.5">
                  <span className="inline-flex items-center rounded-full bg-primary/10 px-2 py-0.5 text-xs font-medium text-primary">
                    {exp.domain.replace('_', ' ')}
                  </span>
                </div>
                <div className="flex items-center justify-between text-xs text-muted-foreground">
                  <Link to={`/labs/${exp.labSlug}/workspace`} className="hover:text-primary transition-colors">
                    {exp.labName}
                  </Link>
                  <span>{exp.agentCount} agents</span>
                </div>
                {/* Metrics */}
                <div className="flex flex-wrap gap-x-3 gap-y-1 text-xs text-muted-foreground">
                  {Object.entries(exp.metrics).map(([key, value]) => (
                    <span key={key}>
                      {key.replace(/_/g, ' ')}: <span className="font-medium text-foreground">{value.toLocaleString()}</span>
                    </span>
                  ))}
                </div>
              </CardContent>
            </Card>
          )
        })}
      </div>
    </div>
  )
}
