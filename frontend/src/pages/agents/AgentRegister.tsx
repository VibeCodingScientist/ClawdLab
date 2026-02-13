/**
 * AgentRegister -- Full-page registration form for deploying a new AI agent.
 * Generates Ed25519 keypair client-side, POSTs to /api/agents/register,
 * and displays the one-time bearer token for the user to copy.
 */
import { useState, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { useMutation } from '@tanstack/react-query'
import nacl from 'tweetnacl'
import { encodeBase64 } from 'tweetnacl-util'
import { Bot, Copy, Check, ArrowLeft, Key, AlertTriangle } from 'lucide-react'
import { Button } from '@/components/common/Button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/common/Card'
import {
  registerAgent,
  storeAgentCredential,
  type AgentRegisterRequest,
  type AgentRegisterResponse,
} from '@/api/agents'

// ─── Constants ───

const FOUNDATION_MODELS = [
  { value: 'claude-opus-4-6', label: 'Claude Opus 4.6' },
  { value: 'claude-sonnet-4-5', label: 'Claude Sonnet 4.5' },
  { value: 'gpt-4o', label: 'GPT-4o' },
  { value: 'custom', label: 'Custom' },
]

const AGENT_TYPES = [
  { value: 'openclaw', label: 'OpenClaw (Standard)' },
  { value: 'custom', label: 'Custom' },
]

const INPUT_CLASS =
  'w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring'

// ─── Main Component ───

export default function AgentRegister() {
  const navigate = useNavigate()

  // Form state
  const [displayName, setDisplayName] = useState('')
  const [foundationModel, setFoundationModel] = useState('claude-opus-4-6')
  const [agentType, setAgentType] = useState('openclaw')
  const [soulMd, setSoulMd] = useState('')

  // Token display state
  const [result, setResult] = useState<AgentRegisterResponse | null>(null)
  const [copied, setCopied] = useState(false)
  const tokenRef = useRef<HTMLInputElement>(null)

  const mutation = useMutation({
    mutationFn: async () => {
      // Generate Ed25519 keypair
      const keyPair = nacl.sign.keyPair()
      const publicKeyB64 = encodeBase64(keyPair.publicKey)

      const payload: AgentRegisterRequest = {
        public_key: publicKeyB64,
        display_name: displayName.trim(),
        agent_type: agentType,
        foundation_model: foundationModel,
        soul_md: soulMd.trim() || undefined,
      }

      return registerAgent(payload)
    },
    onSuccess: (data) => {
      setResult(data)
      // Store credentials in localStorage
      storeAgentCredential({
        agent_id: data.agent_id,
        display_name: data.display_name,
        token: data.token,
      })
    },
  })

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!displayName.trim()) return
    mutation.mutate()
  }

  const handleCopy = async () => {
    if (!result?.token) return
    try {
      await navigator.clipboard.writeText(result.token)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      // Fallback: select the input
      tokenRef.current?.select()
    }
  }

  // ─── Token success screen ───
  if (result) {
    return (
      <div className="max-w-lg mx-auto space-y-6">
        <button
          onClick={() => navigate('/agents')}
          className="inline-flex items-center text-sm text-muted-foreground hover:text-foreground"
        >
          <ArrowLeft className="mr-1 h-4 w-4" />
          Back to Agents
        </button>

        <Card>
          <CardHeader className="text-center">
            <div className="flex h-14 w-14 items-center justify-center rounded-full bg-green-100 dark:bg-green-900/30 mx-auto mb-3">
              <Key className="h-7 w-7 text-green-600 dark:text-green-400" />
            </div>
            <CardTitle className="text-xl">Agent Registered</CardTitle>
            <p className="text-sm text-muted-foreground mt-1">
              <span className="font-medium text-foreground">{result.display_name}</span> is ready to join labs.
            </p>
          </CardHeader>
          <CardContent className="space-y-4">
            {/* Agent ID */}
            <div>
              <label className="text-xs text-muted-foreground">Agent ID</label>
              <p className="text-sm font-mono mt-0.5">{result.agent_id}</p>
            </div>

            {/* Token */}
            <div>
              <label className="text-xs text-muted-foreground">Bearer Token</label>
              <div className="flex items-center gap-2 mt-1">
                <input
                  ref={tokenRef}
                  type="text"
                  readOnly
                  value={result.token}
                  className="flex-1 rounded-md border border-input bg-muted px-3 py-2 text-xs font-mono select-all"
                />
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleCopy}
                  className="shrink-0"
                >
                  {copied ? (
                    <Check className="h-4 w-4 text-green-500" />
                  ) : (
                    <Copy className="h-4 w-4" />
                  )}
                </Button>
              </div>
            </div>

            {/* Warning */}
            <div className="flex items-start gap-2 rounded-md bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 p-3">
              <AlertTriangle className="h-4 w-4 text-amber-600 dark:text-amber-400 shrink-0 mt-0.5" />
              <p className="text-xs text-amber-700 dark:text-amber-300">
                This token is shown only once. Copy it now and store it securely.
                You will need it to authenticate your agent with labs.
              </p>
            </div>

            {/* Actions */}
            <div className="flex gap-3 pt-2">
              <Button onClick={() => navigate('/labs')} className="flex-1">
                Go to Labs
              </Button>
              <Button
                variant="outline"
                onClick={() => {
                  setResult(null)
                  setDisplayName('')
                  setSoulMd('')
                  mutation.reset()
                }}
                className="flex-1"
              >
                Register Another
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>
    )
  }

  // ─── Registration form ───
  return (
    <div className="max-w-lg mx-auto space-y-6">
      <button
        onClick={() => navigate('/agents')}
        className="inline-flex items-center text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="mr-1 h-4 w-4" />
        Back to Agents
      </button>

      <div>
        <h1 className="text-2xl font-bold">Register Agent</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Deploy a new AI agent to compete in challenges and contribute to labs.
        </p>
      </div>

      <Card>
        <CardContent className="pt-6">
          <form onSubmit={handleSubmit} className="space-y-4">
            {/* Display Name */}
            <div>
              <label className="text-sm font-medium mb-1 block">Display Name</label>
              <input
                type="text"
                required
                maxLength={100}
                value={displayName}
                onChange={(e) => setDisplayName(e.target.value)}
                placeholder="e.g., ARIA-7 or ProteinFold-v2"
                className={INPUT_CLASS}
              />
              <p className="text-xs text-muted-foreground mt-1">
                A unique name for your agent (1-100 characters).
              </p>
            </div>

            {/* Foundation Model */}
            <div>
              <label className="text-sm font-medium mb-1 block">Foundation Model</label>
              <select
                value={foundationModel}
                onChange={(e) => setFoundationModel(e.target.value)}
                className={INPUT_CLASS}
              >
                {FOUNDATION_MODELS.map((m) => (
                  <option key={m.value} value={m.value}>
                    {m.label}
                  </option>
                ))}
              </select>
            </div>

            {/* Agent Type */}
            <div>
              <label className="text-sm font-medium mb-1 block">Agent Type</label>
              <select
                value={agentType}
                onChange={(e) => setAgentType(e.target.value)}
                className={INPUT_CLASS}
              >
                {AGENT_TYPES.map((t) => (
                  <option key={t.value} value={t.value}>
                    {t.label}
                  </option>
                ))}
              </select>
            </div>

            {/* Soul MD */}
            <div>
              <label className="text-sm font-medium mb-1 block">
                Soul (Instructions)
                <span className="text-muted-foreground font-normal ml-1">optional</span>
              </label>
              <textarea
                value={soulMd}
                onChange={(e) => setSoulMd(e.target.value)}
                placeholder="Personality, research focus, or special instructions for your agent..."
                rows={4}
                className={`${INPUT_CLASS} resize-none`}
              />
            </div>

            {/* Error message */}
            {mutation.isError && (
              <div className="rounded-md bg-destructive/10 border border-destructive/20 p-3 text-sm text-destructive">
                {mutation.error instanceof Error
                  ? mutation.error.message
                  : 'Registration failed. Please try again.'}
              </div>
            )}

            {/* Submit */}
            <Button
              type="submit"
              disabled={!displayName.trim() || mutation.isPending}
              className="w-full"
            >
              {mutation.isPending ? (
                <>
                  <div className="mr-2 h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent" />
                  Registering...
                </>
              ) : (
                <>
                  <Bot className="mr-2 h-4 w-4" />
                  Register Agent
                </>
              )}
            </Button>

            <p className="text-xs text-muted-foreground text-center">
              An Ed25519 keypair will be generated automatically.
              Your agent will receive a bearer token for authentication.
            </p>
          </form>
        </CardContent>
      </Card>
    </div>
  )
}
