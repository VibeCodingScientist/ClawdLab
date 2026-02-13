/**
 * JoinLabDialog -- Reusable Radix Dialog for committing an agent to a lab.
 * Reads agent credentials from localStorage, lets user pick an agent + role,
 * and POSTs to /api/labs/{slug}/join with the agent's bearer token.
 */
import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import * as Dialog from '@radix-ui/react-dialog'
import { Bot, X, Check, AlertTriangle } from 'lucide-react'
import { Button } from '@/components/common/Button'
import {
  getStoredAgents,
  joinLab,
  type StoredAgentCredential,
  type JoinLabResponse,
} from '@/api/agents'

// ─── Constants ───

const ROLES = [
  { value: 'pi', label: 'Principal Investigator', description: 'Leads the lab, sets research direction' },
  { value: 'scout', label: 'Literature Scout', description: 'Finds and retrieves relevant papers' },
  { value: 'research_analyst', label: 'Research Analyst', description: 'Analyzes data and extracts findings' },
  { value: 'skeptical_theorist', label: 'Skeptical Theorist', description: 'Challenges assumptions and identifies gaps' },
  { value: 'synthesizer', label: 'Synthesizer', description: 'Combines findings into coherent narratives' },
]

const INPUT_CLASS =
  'w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring'

// ─── Props ───

interface JoinLabDialogProps {
  slug: string
  onJoined?: () => void
}

// ─── Component ───

export function JoinLabDialog({ slug, onJoined }: JoinLabDialogProps) {
  const [open, setOpen] = useState(false)
  const [agents, setAgents] = useState<StoredAgentCredential[]>([])
  const [selectedAgentId, setSelectedAgentId] = useState('')
  const [selectedRole, setSelectedRole] = useState('scout')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<JoinLabResponse | null>(null)

  // Load agents from localStorage when dialog opens
  useEffect(() => {
    if (open) {
      const stored = getStoredAgents()
      setAgents(stored)
      if (stored.length > 0 && !selectedAgentId) {
        setSelectedAgentId(stored[0].agent_id)
      }
      setError(null)
      setSuccess(null)
    }
  }, [open, selectedAgentId])

  const handleSubmit = async () => {
    const agent = agents.find(a => a.agent_id === selectedAgentId)
    if (!agent) return

    setSubmitting(true)
    setError(null)

    try {
      const result = await joinLab(slug, selectedRole, agent.token)
      setSuccess(result)
      onJoined?.()
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to join lab')
    } finally {
      setSubmitting(false)
    }
  }

  const handleClose = () => {
    setOpen(false)
    // Reset state after closing animation
    setTimeout(() => {
      setError(null)
      setSuccess(null)
      setSubmitting(false)
    }, 200)
  }

  return (
    <Dialog.Root open={open} onOpenChange={setOpen}>
      <Dialog.Trigger asChild>
        <Button variant="outline" size="sm">
          <Bot className="mr-2 h-3.5 w-3.5" />
          Commit Agent
        </Button>
      </Dialog.Trigger>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 bg-black/50 z-50" />
        <Dialog.Content className="fixed left-1/2 top-1/2 z-50 w-full max-w-md -translate-x-1/2 -translate-y-1/2 rounded-lg border bg-card p-6 shadow-lg">
          <div className="flex items-center justify-between mb-4">
            <Dialog.Title className="text-lg font-semibold">Commit Agent to Lab</Dialog.Title>
            <Dialog.Close asChild>
              <button className="rounded-md p-1 hover:bg-muted">
                <X className="h-4 w-4" />
              </button>
            </Dialog.Close>
          </div>

          {/* Success state */}
          {success ? (
            <div className="text-center py-6 space-y-3">
              <div className="flex h-12 w-12 items-center justify-center rounded-full bg-green-100 dark:bg-green-900/30 mx-auto">
                <Check className="h-6 w-6 text-green-600 dark:text-green-400" />
              </div>
              <div>
                <p className="font-medium">Agent joined!</p>
                <p className="text-sm text-muted-foreground mt-1">
                  <span className="font-medium text-foreground">{success.agent_display_name}</span>
                  {' '}is now a{' '}
                  <span className="font-medium text-foreground">
                    {ROLES.find(r => r.value === success.role)?.label ?? success.role}
                  </span>
                  {' '}in this lab.
                </p>
              </div>
              <Button onClick={handleClose} className="mt-2">Done</Button>
            </div>
          ) : agents.length === 0 ? (
            /* No agents registered */
            <div className="text-center py-6 space-y-3">
              <div className="flex h-12 w-12 items-center justify-center rounded-full bg-muted mx-auto">
                <AlertTriangle className="h-6 w-6 text-muted-foreground" />
              </div>
              <div>
                <p className="font-medium">No agents registered</p>
                <p className="text-sm text-muted-foreground mt-1">
                  You need to register an agent before joining a lab.
                </p>
              </div>
              <Dialog.Close asChild>
                <Link to="/agents/register">
                  <Button>Register an Agent</Button>
                </Link>
              </Dialog.Close>
            </div>
          ) : (
            /* Form */
            <div className="space-y-4">
              <Dialog.Description className="text-sm text-muted-foreground">
                Select an agent and role to join <span className="font-medium text-foreground">{slug}</span>.
              </Dialog.Description>

              {/* Agent selector */}
              <div>
                <label className="text-sm font-medium mb-1 block">Agent</label>
                <select
                  value={selectedAgentId}
                  onChange={(e) => setSelectedAgentId(e.target.value)}
                  className={INPUT_CLASS}
                >
                  {agents.map((a) => (
                    <option key={a.agent_id} value={a.agent_id}>
                      {a.display_name}
                    </option>
                  ))}
                </select>
              </div>

              {/* Role selector */}
              <div>
                <label className="text-sm font-medium mb-1 block">Role</label>
                <select
                  value={selectedRole}
                  onChange={(e) => setSelectedRole(e.target.value)}
                  className={INPUT_CLASS}
                >
                  {ROLES.map((r) => (
                    <option key={r.value} value={r.value}>
                      {r.label}
                    </option>
                  ))}
                </select>
                <p className="text-xs text-muted-foreground mt-1">
                  {ROLES.find(r => r.value === selectedRole)?.description}
                </p>
              </div>

              {/* Error */}
              {error && (
                <div className="rounded-md bg-destructive/10 border border-destructive/20 p-3 text-sm text-destructive">
                  {error}
                </div>
              )}

              {/* Actions */}
              <div className="flex justify-end gap-2">
                <Dialog.Close asChild>
                  <Button variant="outline">Cancel</Button>
                </Dialog.Close>
                <Button
                  onClick={handleSubmit}
                  disabled={!selectedAgentId || submitting}
                >
                  {submitting ? (
                    <>
                      <div className="mr-2 h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent" />
                      Joining...
                    </>
                  ) : (
                    'Join Lab'
                  )}
                </Button>
              </div>
            </div>
          )}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  )
}
