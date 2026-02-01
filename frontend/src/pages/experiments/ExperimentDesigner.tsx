/**
 * Experiment designer page
 */

import { useParams, Link } from 'react-router-dom'
import { ArrowLeft } from 'lucide-react'
import { Button } from '@/components/common/Button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/common/Card'

export default function ExperimentDesigner() {
  const { experimentId } = useParams<{ experimentId: string }>()
  const isEditing = !!experimentId

  return (
    <div className="space-y-6">
      <Link to="/experiments">
        <Button variant="ghost" size="sm">
          <ArrowLeft className="mr-2 h-4 w-4" />
          Back to Experiments
        </Button>
      </Link>

      <div>
        <h1 className="text-3xl font-bold">
          {isEditing ? 'Edit Experiment' : 'New Experiment'}
        </h1>
        <p className="text-muted-foreground">
          {isEditing ? 'Modify experiment configuration' : 'Design a new research experiment'}
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Experiment Configuration</CardTitle>
          <CardDescription>Define the parameters for your experiment</CardDescription>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">
            Experiment designer form coming soon...
          </p>
        </CardContent>
      </Card>
    </div>
  )
}
