/**
 * API Keys management page
 */

import { useState } from 'react'
import { Key, Plus, Copy, Trash2 } from 'lucide-react'
import { Button } from '@/components/common/Button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/common/Card'

interface ApiKey {
  id: string
  name: string
  prefix: string
  createdAt: string
  lastUsed?: string
  scopes: string[]
}

// Mock data
const mockKeys: ApiKey[] = [
  {
    id: '1',
    name: 'Development Key',
    prefix: 'clab_dev_xxx',
    createdAt: '2025-01-15',
    lastUsed: '2025-01-20',
    scopes: ['read', 'write'],
  },
  {
    id: '2',
    name: 'Production Key',
    prefix: 'clab_prod_xxx',
    createdAt: '2025-01-10',
    scopes: ['read'],
  },
]

export default function ApiKeys() {
  const [keys] = useState<ApiKey[]>(mockKeys)
  const [, setShowCreateModal] = useState(false)

  return (
    <div className="space-y-6 max-w-4xl">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">API Keys</h1>
          <p className="text-muted-foreground">
            Manage your API keys for programmatic access
          </p>
        </div>
        <Button onClick={() => setShowCreateModal(true)}>
          <Plus className="mr-2 h-4 w-4" />
          Create Key
        </Button>
      </div>

      {/* Keys list */}
      <Card>
        <CardHeader>
          <CardTitle>Your API Keys</CardTitle>
          <CardDescription>
            Use these keys to authenticate API requests
          </CardDescription>
        </CardHeader>
        <CardContent>
          {keys.length > 0 ? (
            <div className="space-y-4">
              {keys.map((key) => (
                <div
                  key={key.id}
                  className="flex items-center justify-between rounded-lg border p-4"
                >
                  <div className="flex items-center gap-4">
                    <div className="flex h-10 w-10 items-center justify-center rounded-full bg-primary/10">
                      <Key className="h-5 w-5 text-primary" />
                    </div>
                    <div>
                      <p className="font-medium">{key.name}</p>
                      <p className="text-sm text-muted-foreground font-mono">
                        {key.prefix}...
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-4">
                    <div className="text-right text-sm">
                      <p className="text-muted-foreground">Created: {key.createdAt}</p>
                      {key.lastUsed && (
                        <p className="text-muted-foreground">Last used: {key.lastUsed}</p>
                      )}
                    </div>
                    <div className="flex gap-2">
                      <Button variant="ghost" size="icon">
                        <Copy className="h-4 w-4" />
                      </Button>
                      <Button variant="ghost" size="icon" className="text-destructive">
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center py-12">
              <Key className="h-12 w-12 text-muted-foreground/50" />
              <h3 className="mt-4 text-lg font-semibold">No API keys</h3>
              <p className="text-sm text-muted-foreground">
                Create your first API key to get started
              </p>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Usage instructions */}
      <Card>
        <CardHeader>
          <CardTitle>Using API Keys</CardTitle>
          <CardDescription>How to authenticate your API requests</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-sm">
            Include your API key in the request header:
          </p>
          <pre className="rounded-md bg-muted p-4 text-sm font-mono overflow-x-auto">
            {`curl -H "X-API-Key: clab_your_key_here" \\
  https://api.clawdlab.example.com/api/v1/agents`}
          </pre>
          <p className="text-sm text-muted-foreground">
            Keep your API keys secure and never share them in public repositories.
          </p>
        </CardContent>
      </Card>
    </div>
  )
}
