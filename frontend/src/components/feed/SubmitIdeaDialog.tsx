/**
 * SubmitIdeaDialog -- Extracted from ForumPage for reuse in IdeasAndLabsFeed.
 * Radix Dialog for submitting a new idea/forum post.
 */
import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import * as Dialog from '@radix-ui/react-dialog'
import { Plus, X, Lightbulb } from 'lucide-react'
import { Button } from '@/components/common/Button'
import { createForumPost } from '@/api/forum'
import type { ForumDomain, ForumPostCreate } from '@/types/forum'

const DOMAIN_OPTIONS: { value: string; label: string }[] = [
  { value: 'computational_biology', label: 'Computational Biology' },
  { value: 'ml_ai', label: 'ML / AI' },
  { value: 'mathematics', label: 'Mathematics' },
  { value: 'materials_science', label: 'Materials Science' },
  { value: 'bioinformatics', label: 'Bioinformatics' },
  { value: 'general', label: 'General' },
]

export function SubmitIdeaDialog({
  authorName,
  onCreated,
}: {
  authorName: string
  onCreated: () => void
}) {
  const [open, setOpen] = useState(false)
  const [title, setTitle] = useState('')
  const [body, setBody] = useState('')
  const [domain, setDomain] = useState<ForumDomain>('general')
  const [submitted, setSubmitted] = useState(false)

  const createMutation = useMutation({
    mutationFn: (data: ForumPostCreate) => createForumPost(data),
    onSuccess: () => {
      setSubmitted(true)
      onCreated()
      setTimeout(() => {
        setOpen(false)
        setTitle('')
        setBody('')
        setDomain('general')
        setSubmitted(false)
      }, 1500)
    },
  })

  const handleSubmit = () => {
    if (!title.trim() || !body.trim()) return
    createMutation.mutate({
      title: title.trim(),
      body: body.trim(),
      domain,
      authorName,
    })
  }

  return (
    <Dialog.Root open={open} onOpenChange={setOpen}>
      <Dialog.Trigger asChild>
        <Button>
          <Plus className="mr-1.5 h-4 w-4" />
          Submit Your Idea
        </Button>
      </Dialog.Trigger>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 bg-black/50 z-50" />
        <Dialog.Content className="fixed left-1/2 top-1/2 z-50 w-full max-w-lg -translate-x-1/2 -translate-y-1/2 rounded-lg border bg-card p-6 shadow-lg">
          <div className="flex items-center justify-between mb-4">
            <Dialog.Title className="text-lg font-semibold">
              Submit Your Idea
            </Dialog.Title>
            <Dialog.Close asChild>
              <button className="rounded-md p-1 hover:bg-muted">
                <X className="h-4 w-4" />
              </button>
            </Dialog.Close>
          </div>

          {submitted ? (
            <div className="text-center py-8">
              <Lightbulb className="h-10 w-10 text-amber-400 mx-auto mb-3" />
              <p className="font-medium">Idea submitted!</p>
              <p className="text-sm text-muted-foreground mt-1">
                Your post is now visible in the feed.
              </p>
            </div>
          ) : (
            <div className="space-y-4">
              <Dialog.Description className="text-sm text-muted-foreground">
                Propose an experiment, share a hypothesis, or start a discussion.
              </Dialog.Description>

              <div>
                <label className="text-sm font-medium mb-1 block">Title</label>
                <input
                  type="text"
                  value={title}
                  onChange={e => setTitle(e.target.value)}
                  placeholder="A concise title for your idea"
                  className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                />
              </div>

              <div>
                <label className="text-sm font-medium mb-1 block">Domain</label>
                <select
                  value={domain}
                  onChange={e => setDomain(e.target.value as ForumDomain)}
                  className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                >
                  {DOMAIN_OPTIONS.map(f => (
                    <option key={f.value} value={f.value}>
                      {f.label}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="text-sm font-medium mb-1 block">Details</label>
                <textarea
                  value={body}
                  onChange={e => setBody(e.target.value)}
                  placeholder="Describe your idea, hypothesis, or question..."
                  rows={5}
                  className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring resize-none"
                />
              </div>

              <div className="flex justify-end gap-2">
                <Dialog.Close asChild>
                  <Button variant="outline">Cancel</Button>
                </Dialog.Close>
                <Button
                  onClick={handleSubmit}
                  disabled={!title.trim() || !body.trim() || createMutation.isPending}
                >
                  {createMutation.isPending ? 'Submitting...' : 'Submit'}
                </Button>
              </div>
            </div>
          )}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  )
}
