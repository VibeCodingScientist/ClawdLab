/**
 * Experiment list page
 */

import { Link } from 'react-router-dom'
import { FlaskConical, Plus } from 'lucide-react'
import { Button } from '@/components/common/Button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/common/Card'

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

      <Card>
        <CardContent className="flex flex-col items-center justify-center py-12">
          <FlaskConical className="h-12 w-12 text-muted-foreground/50" />
          <h3 className="mt-4 text-lg font-semibold">No experiments yet</h3>
          <p className="text-sm text-muted-foreground">
            Create your first experiment to get started
          </p>
          <Link to="/experiments/new">
            <Button className="mt-4">
              <Plus className="mr-2 h-4 w-4" />
              Create Experiment
            </Button>
          </Link>
        </CardContent>
      </Card>
    </div>
  )
}
