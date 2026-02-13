/**
 * SuggestToLab -- Button + Dialog for humans to submit suggestions to a lab.
 * Uses Radix Dialog + local state. Shows toast on submit.
 * Also creates a forum post (fire-and-forget) when not in mock mode.
 * Depends on: @radix-ui/react-dialog, @radix-ui/react-select, lucide-react
 */
import { useState } from 'react'
import * as Dialog from '@radix-ui/react-dialog'
import { Lightbulb, X } from 'lucide-react'
import { Button } from '@/components/common/Button'
import { useAuth } from '@/hooks/useAuth'
import { createForumPost, postLabDiscussion } from '@/api/forum'

const CATEGORIES = [
  { value: 'hypothesis', label: 'Hypothesis' },
  { value: 'methodology', label: 'Methodology' },
  { value: 'data_source', label: 'Data Source' },
  { value: 'other', label: 'Other' },
]

interface SuggestToLabProps {
  slug?: string
  onSuggestionSubmitted?: (text: string, category: string) => void
}

export function SuggestToLab({ slug, onSuggestionSubmitted }: SuggestToLabProps) {
  const { user } = useAuth()
  const [open, setOpen] = useState(false)
  const [title, setTitle] = useState('')
  const [text, setText] = useState('')
  const [category, setCategory] = useState('hypothesis')
  const [submitted, setSubmitted] = useState(false)

  const handleSubmit = () => {
    if (!text.trim()) return
    // Fire workspace callback (for narrative)
    onSuggestionSubmitted?.(text.trim(), category)

    const username = user?.username ?? 'anonymous'
    const suggestionTitle = title.trim() || `Lab suggestion: ${category}`

    // Fire-and-forget: create a forum post
    createForumPost({
      title: suggestionTitle,
      body: text.trim(),
      domain: 'general',
      authorName: username,
    }).catch(err => {
      console.warn('Failed to create forum post from suggestion:', err)
    })

    // Also post to lab discussion so it shows in the chat panel
    if (slug) {
      postLabDiscussion(slug, {
        body: `**[Suggestion: ${category}]** ${suggestionTitle}\n\n${text.trim()}`,
        authorName: username,
      }).catch(err => {
        console.warn('Failed to post discussion from suggestion:', err)
      })
    }

    setSubmitted(true)
    setTimeout(() => {
      setOpen(false)
      setTitle('')
      setText('')
      setCategory('hypothesis')
      setSubmitted(false)
    }, 1500)
  }

  return (
    <Dialog.Root open={open} onOpenChange={setOpen}>
      <Dialog.Trigger asChild>
        <Button variant="outline" size="sm">
          <Lightbulb className="mr-1.5 h-3.5 w-3.5 text-amber-400" />
          Suggest to Lab
        </Button>
      </Dialog.Trigger>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 bg-black/50 z-50" />
        <Dialog.Content className="fixed left-1/2 top-1/2 z-50 w-full max-w-md -translate-x-1/2 -translate-y-1/2 rounded-lg border bg-card p-6 shadow-lg">
          <div className="flex items-center justify-between mb-4">
            <Dialog.Title className="text-lg font-semibold">
              Suggest to Lab
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
              <p className="font-medium">Suggestion submitted!</p>
              <p className="text-sm text-muted-foreground mt-1">
                The lab agents will consider your input.
              </p>
            </div>
          ) : (
            <div className="space-y-4">
              <Dialog.Description className="text-sm text-muted-foreground">
                Share your idea with the lab agents. Your suggestion will appear in the lab narrative and the forum.
              </Dialog.Description>

              <div>
                <label className="text-sm font-medium mb-1 block">Title</label>
                <input
                  type="text"
                  value={title}
                  onChange={e => setTitle(e.target.value)}
                  placeholder="A short title for your suggestion"
                  className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                />
              </div>

              <div>
                <label className="text-sm font-medium mb-1 block">Category</label>
                <select
                  value={category}
                  onChange={e => setCategory(e.target.value)}
                  className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                >
                  {CATEGORIES.map(c => (
                    <option key={c.value} value={c.value}>{c.label}</option>
                  ))}
                </select>
              </div>

              <div>
                <label className="text-sm font-medium mb-1 block">Your suggestion</label>
                <textarea
                  value={text}
                  onChange={e => setText(e.target.value)}
                  placeholder="Share your idea with the lab agents..."
                  rows={4}
                  className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring resize-none"
                />
              </div>

              <div className="flex justify-end gap-2">
                <Dialog.Close asChild>
                  <Button variant="outline">Cancel</Button>
                </Dialog.Close>
                <Button onClick={handleSubmit} disabled={!text.trim()}>
                  Submit Suggestion
                </Button>
              </div>
            </div>
          )}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  )
}
