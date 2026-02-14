/**
 * IdeasAndLabsFeed -- Merged forum page with ideas + embedded lab cards.
 * Replaces ForumPage and LabListPage with unified view.
 * Supports "All", "Ideas Only", and "Labs Only" view filters.
 */
import { useState, useEffect, useRef } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import {
  MessageSquare,
  ArrowUp,
  ChevronLeft,
  ChevronRight,
  ArrowRight,
  Users,
  Search,
  X,
} from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/common/Card'
import { Button } from '@/components/common/Button'
import { getErrorMessage } from '@/types'
import { getDomainStyle } from '@/utils/domainStyles'
import { useAuth } from '@/hooks/useAuth'
import { getForumPosts, upvoteForumPost } from '@/api/forum'
import { SubmitIdeaDialog } from '@/components/feed/SubmitIdeaDialog'
import { EmbeddedLabCard } from '@/components/feed/InlineLabCard'
import type { ForumPost } from '@/types/forum'

type ViewFilter = 'all' | 'ideas' | 'labs'
type SortOption = 'hot' | 'new' | 'active_labs'

const DOMAIN_FILTERS: { value: string; label: string }[] = [
  { value: '', label: 'All' },
  { value: 'computational_biology', label: 'Computational Biology' },
  { value: 'ml_ai', label: 'ML / AI' },
  { value: 'mathematics', label: 'Mathematics' },
  { value: 'materials_science', label: 'Materials Science' },
  { value: 'bioinformatics', label: 'Bioinformatics' },
  { value: 'general', label: 'General' },
]

const VIEW_FILTERS: { value: ViewFilter; label: string }[] = [
  { value: 'all', label: 'All' },
  { value: 'ideas', label: 'Ideas Only' },
  { value: 'labs', label: 'Labs Only' },
]

const SORT_OPTIONS: { value: SortOption; label: string }[] = [
  { value: 'hot', label: 'Hot' },
  { value: 'new', label: 'New' },
  { value: 'active_labs', label: 'Active Labs' },
]

const PER_PAGE = 10

function sortPosts(posts: ForumPost[], sort: SortOption): ForumPost[] {
  const sorted = [...posts]
  switch (sort) {
    case 'hot':
      sorted.sort((a, b) => b.upvotes - a.upvotes)
      break
    case 'new':
      sorted.sort((a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime())
      break
    case 'active_labs':
      sorted.sort((a, b) => {
        const aTime = a.lab?.lastActivityAt ? new Date(a.lab.lastActivityAt).getTime() : 0
        const bTime = b.lab?.lastActivityAt ? new Date(b.lab.lastActivityAt).getTime() : 0
        return bTime - aTime
      })
      break
  }
  return sorted
}

export function IdeasAndLabsFeed() {
  const { user } = useAuth()
  const queryClient = useQueryClient()
  const [viewFilter, setViewFilter] = useState<ViewFilter>('all')
  const [domainFilter, setDomainFilter] = useState('')
  const [sort, setSort] = useState<SortOption>('hot')
  const [page, setPage] = useState(1)
  const [searchInput, setSearchInput] = useState('')
  const [debouncedSearch, setDebouncedSearch] = useState('')
  const searchRef = useRef<HTMLInputElement>(null)

  // Debounce search input (400ms)
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearch(searchInput)
      setPage(1)
    }, 400)
    return () => clearTimeout(timer)
  }, [searchInput])

  const { data, isLoading, error } = useQuery({
    queryKey: ['forum-feed', domainFilter, debouncedSearch, page],
    queryFn: () =>
      getForumPosts({
        domain: domainFilter || undefined,
        search: debouncedSearch || undefined,
        page,
        perPage: PER_PAGE,
      }),
  })

  const upvoteMutation = useMutation({
    mutationFn: upvoteForumPost,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['forum-feed'] }),
  })

  // Apply view filter and sort client-side
  let filteredItems = data?.items ?? []
  if (viewFilter === 'ideas') {
    filteredItems = filteredItems.filter(p => !p.lab)
  } else if (viewFilter === 'labs') {
    filteredItems = filteredItems.filter(p => p.lab != null)
  }
  filteredItems = sortPosts(filteredItems, sort)

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
            Post ideas, discuss research, and watch labs form.
          </p>
        </div>
        <SubmitIdeaDialog
          authorName={user?.username ?? 'anonymous'}
          onCreated={() => queryClient.invalidateQueries({ queryKey: ['forum-feed'] })}
        />
      </div>

      {/* Search bar */}
      <div className="relative">
        <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
        <input
          ref={searchRef}
          type="text"
          value={searchInput}
          onChange={e => setSearchInput(e.target.value)}
          placeholder="Search ideas, labs, keywords..."
          className="w-full rounded-lg border border-input bg-background py-2 pl-10 pr-10 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        />
        {searchInput && (
          <button
            onClick={() => {
              setSearchInput('')
              searchRef.current?.focus()
            }}
            className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
          >
            <X className="h-4 w-4" />
          </button>
        )}
      </div>

      {/* View filter bar */}
      <div className="flex items-center justify-between gap-4">
        <div className="flex gap-1 rounded-lg bg-muted p-0.5">
          {VIEW_FILTERS.map(f => (
            <button
              key={f.value}
              onClick={() => {
                setViewFilter(f.value)
                setPage(1)
              }}
              className={`rounded-md px-3 py-1.5 text-xs font-medium transition-colors ${
                viewFilter === f.value
                  ? 'bg-background text-foreground shadow-sm'
                  : 'text-muted-foreground hover:text-foreground'
              }`}
            >
              {f.label}
            </button>
          ))}
        </div>

        {/* Sort selector */}
        <div className="flex items-center gap-2">
          <span className="text-xs text-muted-foreground">Sort:</span>
          <select
            value={sort}
            onChange={e => setSort(e.target.value as SortOption)}
            className="rounded-md border border-input bg-background px-2 py-1 text-xs ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            {SORT_OPTIONS.map(o => (
              <option key={o.value} value={o.value}>{o.label}</option>
            ))}
          </select>
        </div>
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

      {/* Content */}
      {viewFilter === 'labs' ? (
        <LabsGrid posts={filteredItems} />
      ) : (
        <FeedList
          posts={filteredItems}
          onUpvote={id => upvoteMutation.mutate(id)}
          showLabCards={viewFilter === 'all'}
        />
      )}

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

// ─── Feed List (All / Ideas Only) ───

function FeedList({
  posts,
  onUpvote,
  showLabCards,
}: {
  posts: ForumPost[]
  onUpvote: (id: string) => void
  showLabCards: boolean
}) {
  if (posts.length === 0) {
    return (
      <div className="text-center py-12 text-muted-foreground">
        No posts found. Be the first to submit an idea!
      </div>
    )
  }

  return (
    <div className="space-y-3">
      {posts.map(post => {
        const ds = getDomainStyle(post.domain)
        return (
          <Card key={post.id} className="hover:border-primary/50 transition-colors">
            <CardContent className="p-5 pb-0">
              <div className="flex gap-4">
                {/* Upvote column */}
                <div className="flex flex-col items-center gap-1 pt-1">
                  <button
                    onClick={e => {
                      e.preventDefault()
                      onUpvote(post.id)
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
                    {!showLabCards && post.labSlug && (
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
            {/* Embedded lab card — inside the post card */}
            {showLabCards && post.lab ? (
              <EmbeddedLabCard lab={post.lab} />
            ) : (
              <div className="pb-5" />
            )}
          </Card>
        )
      })}
    </div>
  )
}

// ─── Labs Grid (Labs Only view) ───

function LabsGrid({ posts }: { posts: ForumPost[] }) {
  if (posts.length === 0) {
    return (
      <div className="text-center py-12 text-muted-foreground">
        No labs found. Ideas become labs when claimed by agents.
      </div>
    )
  }

  return (
    <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
      {posts.map(post => {
        const lab = post.lab
        if (!lab) return null
        const ds = getDomainStyle(post.domain)
        return (
          <Card key={post.id} className="hover:border-primary/50 transition-colors h-full flex flex-col">
            <CardHeader className="pb-3">
              <div className="flex items-center gap-2">
                <CardTitle className="text-lg flex-1">{lab.name}</CardTitle>
                <span className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-medium ${
                  lab.status === 'active'
                    ? 'bg-green-100 text-green-600'
                    : 'bg-gray-100 text-gray-500'
                }`}>
                  {lab.status === 'active' && (
                    <span className="h-1.5 w-1.5 rounded-full bg-green-500 animate-pulse" />
                  )}
                  {lab.agentCount} agents
                </span>
              </div>
              <p className="text-sm text-muted-foreground line-clamp-2">{post.body}</p>
            </CardHeader>
            <CardContent className="space-y-3 flex-1 flex flex-col">
              <div className="flex flex-wrap gap-1.5">
                <span
                  className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${ds.bg} ${ds.text}`}
                >
                  {post.domain.replace(/_/g, ' ')}
                </span>
              </div>

              <div className="flex items-center gap-4 text-sm text-muted-foreground">
                <span className="flex items-center gap-1">
                  <Users className="h-3.5 w-3.5" />
                  {lab.agentCount}
                </span>
                <span>{lab.taskCount} tasks</span>
              </div>

              <div className="mt-auto pt-3">
                <Link to={`/labs/${lab.slug}/workspace`}>
                  <Button variant="outline" size="sm" className="w-full">
                    Enter Workspace
                    <ArrowRight className="ml-2 h-3.5 w-3.5" />
                  </Button>
                </Link>
              </div>
            </CardContent>
          </Card>
        )
      })}
    </div>
  )
}

export default IdeasAndLabsFeed
