/**
 * Knowledge explorer page
 */

import { Brain, Search, Network } from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/common/Card'

export default function KnowledgeExplorer() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold">Knowledge Graph</h1>
        <p className="text-muted-foreground">
          Explore and visualize the research knowledge graph
        </p>
      </div>

      {/* Search */}
      <div className="relative max-w-xl">
        <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
        <input
          type="text"
          placeholder="Search knowledge entries..."
          className="w-full rounded-md border border-input bg-background pl-10 pr-4 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        />
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        {/* Graph visualization placeholder */}
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Network className="h-5 w-5" />
              Knowledge Graph
            </CardTitle>
            <CardDescription>Visual representation of knowledge relationships</CardDescription>
          </CardHeader>
          <CardContent className="h-96 flex items-center justify-center">
            <div className="text-center">
              <Brain className="h-16 w-16 mx-auto text-muted-foreground/50" />
              <p className="mt-4 text-sm text-muted-foreground">
                Interactive graph visualization coming soon...
              </p>
            </div>
          </CardContent>
        </Card>

        {/* Entry details */}
        <Card>
          <CardHeader>
            <CardTitle>Entry Details</CardTitle>
            <CardDescription>Select a node to view details</CardDescription>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground">
              No entry selected
            </p>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
