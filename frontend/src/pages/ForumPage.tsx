/**
 * ForumPage -- Forum list with domain filter pills, post cards, "Submit Your Idea" dialog,
 * upvote buttons, and pagination.
 */
import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import * as Dialog from '@radix-ui/react-dialog'
import {
  MessageSquare,
  ArrowUp,
  Plus,
  X,
  ChevronLeft,
  ChevronRight,
  Lightbulb,
} from 'lucide-react'
import { Card, CardContent } from '@/components/common/Card'
import { Button } from '@/components/common/Button'
import { getErrorMessage } from '@/types'
import { getDomainStyle } from '@/utils/domainStyles'
import { useAuth } from '@/hooks/useAuth'
import { getForumPosts, createForumPost, upvoteForumPost } from '@/api/forum'
import type { ForumDomain, ForumPostCreate } from '@/types/forum'

const DOMAIN_FILTERS: { value: string; label: string }[] = [
  { value: '', label: 'All' },
  { value: 'computational_biology', label: 'Computational Biology' },
  { value: 'ml_ai', label: 'ML / AI' },
  { value: 'mathematics', label: 'Mathematics' },
  { value: 'materials_science', label: 'Materials Science' },
  { value: 'bioinformatics', label: 'Bioinformatics' },
  { value: 'general', label: 'General' },
]

const PER_PAGE = 10

export function ForumPage() {
  const { user } = useAuth()
  const queryClient = useQueryClient()
  const [domainFilter, setDomainFilter] = useState('')
  const [page, setPage] = useState(1)

  const { data, isLoading, error } = useQuery({
    queryKey: ['forum-posts', domainFilter, page],
    queryFn: () =>
      getForumPosts({
        domain: domainFilter || undefined,
        page,
        perPage: PER_PAGE,
      }),
  })

  const upvoteMutation = useMutation({
    mutationFn: upvoteForumPost,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['forum-posts'] }),
  })

  const totalPages = data ? Math.max(1, Math.ceil(data.total / PER_PAGE)) : 1

  if (isLoading) {
    return (
      <div className="space-y-6">
        <h1 className="text-2xl font-bold">Forum</h1>
        <div className="space-y-4">
          {[1, 2, 3].map(i => (
            <Card key={i} className="animate-pulse">
              <CardContent className="p-6">
                <div className="h-5 bg-muted rounded w-3/4 mb-3" />
                <div className="h-4 bg-muted rounded w-full mb-2" />
                <div className="h-4 bg-muted rounded w-2/3" />
              </CardContent>
            </Card>
          ))}
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="space-y-6">
        <h1 className="text-2xl font-bold">Forum</h1>
        <div className="rounded-lg bg-destructive/10 p-4 text-destructive">
          {getErrorMessage(error)}
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Forum</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Share ideas, propose experiments, and discuss research directions
          </p>
        </div>
        <SubmitIdeaDialog
          authorName={user?.username ?? 'anonymous'}
          onCreated={() => queryClient.invalidateQueries({ queryKey: ['forum-posts'] })}
        />
      </div>

      {/* Domain filter pills */}
      <div className="flex flex-wrap gap-2">
        {DOMAIN_FILTERS.map(f => (
          <button
            key={f.value}
            onClick={() => {
              setDomainFilter(f.value)
              setPage(1)
            }}
            className={`rounded-full px-3 py-1 text-xs font-medium transition-colors ${
              domainFilter === f.value
                ? 'bg-primary text-primary-foreground'
                : 'bg-muted text-muted-foreground hover:bg-muted/80'
            }`}
          >
            {f.label}
          </button>
        ))}
      </div>

      {/* Post list */}
      <div className="space-y-3">
        {data?.items.length === 0 && (
          <div className="text-center py-12 text-muted-foreground">
            No posts yet. Be the first to submit an idea!
          </div>
        )}
        {data?.items.map(post => {
          const ds = getDomainStyle(post.domain)
          return (
            <Card
              key={post.id}
              className="hover:border-primary/50 transition-colors"
            >
              <CardContent className="p-5">
                <div className="flex gap-4">
                  {/* Upvote column */}
                  <div className="flex flex-col items-center gap-1 pt-1">
                    <button
                      onClick={e => {
                        e.preventDefault()
                        upvoteMutation.mutate(post.id)
                      }}
                      className="flex flex-col items-center gap-0.5 text-muted-foreground hover:text-primary transition-colors"
                    >
                      <ArrowUp className="h-4 w-4" />
                      <span className="text-xs font-medium">{post.upvotes}</span>
                    </button>
                  </div>

                  {/* Content */}
                  <div className="flex-1 min-w-0">
                    <Link
                      to={`/forum/${post.id}`}
                      className="text-base font-medium hover:text-primary transition-colors line-clamp-1"
                    >
                      {post.title}
                    </Link>
                    <p className="text-sm text-muted-foreground mt-1 line-clamp-2">
                      {post.body}
                    </p>
                    <div className="flex items-center gap-3 mt-2 flex-wrap">
                      <span
                        className={`inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-medium ${ds.bg} ${ds.text}`}
                      >
                        {post.domain.replace(/_/g, ' ')}
                      </span>
                      <span className="text-xs text-muted-foreground">
                        by {post.authorName}
                      </span>
                      <span className="text-xs text-muted-foreground">
                        {new Date(post.createdAt).toLocaleDateString()}
                      </span>
                      <span className="flex items-center gap-1 text-xs text-muted-foreground">
                        <MessageSquare className="h-3 w-3" />
                        {post.commentCount}
                      </span>
                      {post.labSlug && (
                        <Link
                          to={`/labs/${post.labSlug}/workspace`}
                          className="text-xs text-primary hover:underline"
                          onClick={e => e.stopPropagation()}
                        >
                          {post.labSlug}
                        </Link>
                      )}
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>
          )
        })}
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => setPage(p => Math.max(1, p - 1))}
            disabled={page === 1}
          >
            <ChevronLeft className="h-4 w-4" />
          </Button>
          <span className="text-sm text-muted-foreground">
            Page {page} of {totalPages}
          </span>
          <Button
            variant="outline"
            size="sm"
            onClick={() => setPage(p => Math.min(totalPages, p + 1))}
            disabled={page === totalPages}
          >
            <ChevronRight className="h-4 w-4" />
          </Button>
        </div>
      )}
    </div>
  )
}

// ─── Submit Your Idea Dialog ───

function SubmitIdeaDialog({
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
                Your post is now visible in the forum.
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
                  {DOMAIN_FILTERS.filter(f => f.value).map(f => (
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

export default ForumPage
