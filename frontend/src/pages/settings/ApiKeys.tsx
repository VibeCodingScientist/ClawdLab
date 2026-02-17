/**
 * API Keys management page — real CRUD backed by /api/user/api-keys
 */

import { useEffect, useState, useCallback } from 'react'
import { Key, Plus, Trash2, Copy, Check, AlertCircle, Loader2, Link as LinkIcon } from 'lucide-react'
import { Button } from '@/components/common/Button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/common/Card'
import {
  fetchApiKeys,
  createApiKey,
  revokeApiKey,
  type ApiKeyResponse,
  type ApiKeyCreateResponse,
} from '@/api/apiKeys'
import { Link } from 'react-router-dom'

export default function ApiKeys() {
  const [keys, setKeys] = useState<ApiKeyResponse[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // Create modal state
  const [showCreate, setShowCreate] = useState(false)
  const [createName, setCreateName] = useState('')
  const [createExpiry, setCreateExpiry] = useState<string>('none')
  const [creating, setCreating] = useState(false)

  // Token reveal state
  const [newToken, setNewToken] = useState<ApiKeyCreateResponse | null>(null)
  const [copied, setCopied] = useState(false)

  // Delete confirmation
  const [deletingId, setDeletingId] = useState<string | null>(null)

  const loadKeys = useCallback(async () => {
    try {
      setError(null)
      const data = await fetchApiKeys()
      setKeys(data.items)
    } catch {
      setError('Failed to load API keys')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadKeys()
  }, [loadKeys])

  const handleCreate = async () => {
    if (!createName.trim()) return
    setCreating(true)
    setError(null)
    try {
      const expiresInDays = createExpiry === 'none' ? undefined : parseInt(createExpiry, 10)
      const result = await createApiKey({
        name: createName.trim(),
        expires_in_days: expiresInDays ?? null,
      })
      setNewToken(result)
      setShowCreate(false)
      setCreateName('')
      setCreateExpiry('none')
      await loadKeys()
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to create API key'
      setError(msg)
    } finally {
      setCreating(false)
    }
  }

  const handleRevoke = async (keyId: string) => {
    setError(null)
    setDeletingId(keyId)
    try {
      await revokeApiKey(keyId)
      await loadKeys()
    } catch {
      setError('Failed to revoke API key')
    } finally {
      setDeletingId(null)
    }
  }

  const handleCopy = async (text: string) => {
    await navigator.clipboard.writeText(text)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  const formatDate = (dateStr: string | null) => {
    if (!dateStr) return 'Never'
    return new Date(dateStr).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    })
  }

  return (
    <div className="space-y-6 max-w-4xl mx-auto">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">API Keys</h1>
          <p className="text-muted-foreground">
            Manage your API keys for programmatic access
          </p>
        </div>
        <Button onClick={() => setShowCreate(true)}>
          <Plus className="mr-2 h-4 w-4" />
          Create Key
        </Button>
      </div>

      {error && (
        <div className="flex items-center gap-2 rounded-md border border-destructive/50 bg-destructive/10 p-3 text-sm text-destructive">
          <AlertCircle className="h-4 w-4 flex-shrink-0" />
          {error}
        </div>
      )}

      {/* Token reveal modal */}
      {newToken && (
        <Card className="border-green-500/50 bg-green-500/5">
          <CardHeader>
            <CardTitle className="text-green-600">API Key Created</CardTitle>
            <CardDescription>
              Copy your API key now — it will not be shown again.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="flex items-center gap-2">
              <code className="flex-1 rounded-md bg-muted p-3 text-sm font-mono break-all">
                {newToken.token}
              </code>
              <Button
                variant="outline"
                size="icon"
                onClick={() => handleCopy(newToken.token)}
              >
                {copied ? (
                  <Check className="h-4 w-4 text-green-600" />
                ) : (
                  <Copy className="h-4 w-4" />
                )}
              </Button>
            </div>
            <Button variant="outline" size="sm" onClick={() => setNewToken(null)}>
              Done
            </Button>
          </CardContent>
        </Card>
      )}

      {/* Create modal */}
      {showCreate && (
        <Card>
          <CardHeader>
            <CardTitle>Create API Key</CardTitle>
            <CardDescription>
              Create a new long-lived key for programmatic API access
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <label className="text-sm font-medium" htmlFor="key-name">
                Name
              </label>
              <input
                id="key-name"
                type="text"
                placeholder="e.g. Development Key"
                value={createName}
                onChange={(e) => setCreateName(e.target.value)}
                className="mt-1 w-full rounded-md border bg-background px-3 py-2 text-sm"
                maxLength={100}
                autoFocus
              />
            </div>
            <div>
              <label className="text-sm font-medium" htmlFor="key-expiry">
                Expiration
              </label>
              <select
                id="key-expiry"
                value={createExpiry}
                onChange={(e) => setCreateExpiry(e.target.value)}
                className="mt-1 w-full rounded-md border bg-background px-3 py-2 text-sm"
              >
                <option value="none">No expiration</option>
                <option value="30">30 days</option>
                <option value="90">90 days</option>
                <option value="180">180 days</option>
                <option value="365">1 year</option>
              </select>
            </div>
            <div className="flex gap-2">
              <Button onClick={handleCreate} disabled={!createName.trim() || creating}>
                {creating && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                Create
              </Button>
              <Button variant="outline" onClick={() => setShowCreate(false)}>
                Cancel
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Keys list */}
      <Card>
        <CardHeader>
          <CardTitle>Your API Keys</CardTitle>
          <CardDescription>
            Use these keys to authenticate API requests
          </CardDescription>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            </div>
          ) : keys.length > 0 ? (
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
                        {key.token_prefix}...
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-4">
                    <div className="text-right text-sm">
                      <p className="text-muted-foreground">
                        Created: {formatDate(key.created_at)}
                      </p>
                      {key.last_used_at && (
                        <p className="text-muted-foreground">
                          Last used: {formatDate(key.last_used_at)}
                        </p>
                      )}
                      {key.expires_at && (
                        <p className="text-muted-foreground">
                          Expires: {formatDate(key.expires_at)}
                        </p>
                      )}
                    </div>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="text-destructive"
                      onClick={() => handleRevoke(key.id)}
                      disabled={deletingId === key.id}
                    >
                      {deletingId === key.id ? (
                        <Loader2 className="h-4 w-4 animate-spin" />
                      ) : (
                        <Trash2 className="h-4 w-4" />
                      )}
                    </Button>
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
            Include your API key as a Bearer token in the Authorization header:
          </p>
          <pre className="rounded-md bg-muted p-4 text-sm font-mono overflow-x-auto">
            {`curl -H "Authorization: Bearer clab_user_..." \\
  https://clawdlab.xyz/api/security/users/me`}
          </pre>
          <p className="text-sm text-muted-foreground">
            Keep your API keys secure and never share them in public repositories.
          </p>
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <LinkIcon className="h-4 w-4" />
            <Link to="/developers" className="underline hover:text-foreground">
              See the Developer Docs for full API documentation
            </Link>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
