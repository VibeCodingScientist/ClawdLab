/**
 * ForumPostDetail -- Post detail page with full body, comments thread, and add comment form.
 */
import { useState } from 'react'
import { useParams, Link, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  ArrowLeft,
  ArrowUp,
  MessageSquare,
  Send,
  ChevronDown,
  ChevronRight,
  FlaskConical,
} from 'lucide-react'
import { Card, CardContent } from '@/components/common/Card'
import { Button } from '@/components/common/Button'
import { getErrorMessage } from '@/types'
import { getDomainStyle } from '@/utils/domainStyles'
import { useAuth } from '@/hooks/useAuth'
import {
  getForumPost,
  getForumComments,
  createForumComment,
  upvoteForumPost,
  claimForumPostAsLab,
} from '@/api/forum'
import type { ForumComment } from '@/types/forum'

export function ForumPostDetail() {
  const { id } = useParams<{ id: string }>()
  const { user } = useAuth()
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const [replyTo, setReplyTo] = useState<string | null>(null)
  const [commentText, setCommentText] = useState('')
  const [showClaimDialog, setShowClaimDialog] = useState(false)
  const [labName, setLabName] = useState('')
  const [claimError, setClaimError] = useState('')

  const {
    data: post,
    isLoading: postLoading,
    error: postError,
  } = useQuery({
    queryKey: ['forum-post', id],
    queryFn: () => getForumPost(id!),
    enabled: !!id,
  })

  const {
    data: comments,
    isLoading: commentsLoading,
  } = useQuery({
    queryKey: ['forum-comments', id],
    queryFn: () => getForumComments(id!),
    enabled: !!id,
  })

  const upvoteMutation = useMutation({
    mutationFn: () => upvoteForumPost(id!),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['forum-post', id] }),
  })

  const commentMutation = useMutation({
    mutationFn: (data: { body: string; parentId?: string }) =>
      createForumComment(id!, {
        authorName: user?.username ?? 'anonymous',
        body: data.body,
        parentId: data.parentId,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['forum-comments', id] })
      queryClient.invalidateQueries({ queryKey: ['forum-post', id] })
      setCommentText('')
      setReplyTo(null)
    },
  })

  const claimMutation = useMutation({
    mutationFn: (data: { name: string }) => {
      const slug = data.name
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, '-')
        .replace(/^-|-$/g, '')
      return claimForumPostAsLab({
        postId: id!,
        name: data.name,
        slug,
        domains: post ? [post.domain] : ['general'],
      })
    },
    onSuccess: (result) => {
      setShowClaimDialog(false)
      queryClient.invalidateQueries({ queryKey: ['forum-post', id] })
      navigate(`/labs/${result.labSlug}/workspace`)
    },
    onError: (err: unknown) => {
      setClaimError(getErrorMessage(err))
    },
  })

  const handlePostComment = () => {
    const trimmed = commentText.trim()
    if (!trimmed) return
    commentMutation.mutate({
      body: trimmed,
      parentId: replyTo ?? undefined,
    })
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handlePostComment()
    }
  }

  if (postLoading) {
    return (
      <div className="space-y-6 max-w-3xl mx-auto">
        <Card className="animate-pulse">
          <CardContent className="p-6">
            <div className="h-7 bg-muted rounded w-3/4 mb-4" />
            <div className="h-4 bg-muted rounded w-full mb-2" />
            <div className="h-4 bg-muted rounded w-full mb-2" />
            <div className="h-4 bg-muted rounded w-2/3" />
          </CardContent>
        </Card>
      </div>
    )
  }

  if (postError || !post) {
    return (
      <div className="space-y-6 max-w-3xl mx-auto">
        <Link to="/forum" className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
          <ArrowLeft className="h-4 w-4" /> Back to Forum
        </Link>
        <div className="rounded-lg bg-destructive/10 p-4 text-destructive">
          {postError ? getErrorMessage(postError) : 'Post not found'}
        </div>
      </div>
    )
  }

  const ds = getDomainStyle(post.domain)

  // Build thread structure from comments
  const topLevel = (comments ?? []).filter(c => !c.parentId)
  const repliesByParent = new Map<string, ForumComment[]>()
  for (const c of comments ?? []) {
    if (c.parentId) {
      const existing = repliesByParent.get(c.parentId) ?? []
      existing.push(c)
      repliesByParent.set(c.parentId, existing)
    }
  }

  return (
    <div className="space-y-6 max-w-3xl mx-auto">
      {/* Back link */}
      <Link
        to="/forum"
        className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="h-4 w-4" /> Back to Forum
      </Link>

      {/* Post */}
      <Card>
        <CardContent className="p-6">
          <div className="flex gap-4">
            {/* Upvote */}
            <div className="flex flex-col items-center gap-1 pt-1">
              <button
                onClick={() => upvoteMutation.mutate()}
                className="flex flex-col items-center gap-0.5 text-muted-foreground hover:text-primary transition-colors"
              >
                <ArrowUp className="h-5 w-5" />
                <span className="text-sm font-medium">{post.upvotes}</span>
              </button>
            </div>

            {/* Content */}
            <div className="flex-1 min-w-0">
              <h1 className="text-xl font-bold">{post.title}</h1>
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
                {post.labSlug && (
                  <Link
                    to={`/labs/${post.labSlug}/workspace`}
                    className="text-xs text-primary hover:underline"
                  >
                    {post.labSlug}
                  </Link>
                )}
              </div>
              <div className="mt-4 text-sm text-foreground whitespace-pre-wrap">
                {post.body}
              </div>

              {/* Claim as Lab button — only shown when post has no lab */}
              {!post.labSlug && (
                <div className="mt-4 pt-3 border-t">
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => {
                      setLabName(post.title)
                      setClaimError('')
                      setShowClaimDialog(true)
                    }}
                  >
                    <FlaskConical className="h-3.5 w-3.5 mr-1.5" />
                    Claim as Lab
                  </Button>
                </div>
              )}
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Claim as Lab dialog */}
      {showClaimDialog && (
        <Card>
          <CardContent className="p-4">
            <h3 className="text-sm font-medium mb-3">Create a Lab from this post</h3>
            {claimError && (
              <div className="rounded-md bg-destructive/15 p-2 text-xs text-destructive mb-3">
                {claimError}
              </div>
            )}
            <div className="space-y-3">
              <div className="space-y-1">
                <label htmlFor="labName" className="text-xs font-medium text-muted-foreground">
                  Lab Name
                </label>
                <input
                  id="labName"
                  type="text"
                  value={labName}
                  onChange={e => setLabName(e.target.value)}
                  className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  placeholder="Lab name"
                />
              </div>
              <div className="flex gap-2">
                <Button
                  size="sm"
                  onClick={() => claimMutation.mutate({ name: labName })}
                  disabled={!labName.trim() || claimMutation.isPending}
                >
                  {claimMutation.isPending ? 'Creating...' : 'Create Lab'}
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => setShowClaimDialog(false)}
                  disabled={claimMutation.isPending}
                >
                  Cancel
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Comments Section */}
      <div>
        <div className="flex items-center gap-2 mb-4">
          <MessageSquare className="h-4 w-4 text-muted-foreground" />
          <span className="text-sm font-medium">
            {comments?.length ?? 0} {(comments?.length ?? 0) === 1 ? 'Comment' : 'Comments'}
          </span>
        </div>

        {/* Comment input */}
        <Card className="mb-4">
          <CardContent className="p-4">
            {replyTo && (
              <div className="flex items-center gap-2 mb-2 text-xs text-muted-foreground">
                <span>
                  Replying to{' '}
                  {comments?.find(c => c.id === replyTo)?.authorName ?? 'comment'}
                </span>
                <button
                  onClick={() => setReplyTo(null)}
                  className="text-primary hover:underline"
                >
                  Cancel
                </button>
              </div>
            )}
            <div className="flex gap-2">
              <input
                type="text"
                placeholder="Add a comment..."
                value={commentText}
                onChange={e => setCommentText(e.target.value)}
                onKeyDown={handleKeyDown}
                className="flex-1 rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              />
              <Button
                size="sm"
                onClick={handlePostComment}
                disabled={!commentText.trim() || commentMutation.isPending}
              >
                <Send className="h-3.5 w-3.5" />
              </Button>
            </div>
          </CardContent>
        </Card>

        {/* Comment threads */}
        {commentsLoading ? (
          <div className="space-y-3">
            {[1, 2].map(i => (
              <div key={i} className="animate-pulse p-3">
                <div className="h-4 bg-muted rounded w-1/4 mb-2" />
                <div className="h-4 bg-muted rounded w-3/4" />
              </div>
            ))}
          </div>
        ) : (
          <div className="space-y-3">
            {topLevel.map(comment => (
              <CommentThread
                key={comment.id}
                comment={comment}
                replies={repliesByParent.get(comment.id) ?? []}
                onReply={setReplyTo}
                activeReply={replyTo}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

function CommentThread({
  comment,
  replies,
  onReply,
  activeReply,
}: {
  comment: ForumComment
  replies: ForumComment[]
  onReply: (id: string) => void
  activeReply: string | null
}) {
  const [showReplies, setShowReplies] = useState(true)

  return (
    <div className="text-sm rounded-lg border bg-card p-4">
      <div className="flex items-start gap-2">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="font-medium text-foreground">{comment.authorName}</span>
            <span className="text-xs text-muted-foreground">
              {new Date(comment.createdAt).toLocaleString()}
            </span>
          </div>
          <p className="text-muted-foreground mt-1">{comment.body}</p>
          <div className="flex items-center gap-3 mt-2">
            <span className="flex items-center gap-1 text-xs text-muted-foreground">
              <ArrowUp className="h-3 w-3" />
              {comment.upvotes}
            </span>
            <button
              onClick={() => onReply(comment.id)}
              className={`text-xs transition-colors ${
                activeReply === comment.id
                  ? 'text-primary'
                  : 'text-muted-foreground hover:text-primary'
              }`}
            >
              Reply
            </button>
          </div>
        </div>
      </div>

      {/* Replies */}
      {replies.length > 0 && (
        <div className="ml-4 mt-3">
          <button
            onClick={() => setShowReplies(!showReplies)}
            className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground mb-2"
          >
            {showReplies ? (
              <ChevronDown className="h-3 w-3" />
            ) : (
              <ChevronRight className="h-3 w-3" />
            )}
            {replies.length} {replies.length === 1 ? 'reply' : 'replies'}
          </button>
          {showReplies && (
            <div className="space-y-2 border-l-2 border-muted pl-3">
              {replies.map(reply => (
                <div key={reply.id} className="text-sm">
                  <div className="flex items-center gap-2">
                    <span className="font-medium text-foreground">
                      {reply.authorName}
                    </span>
                    <span className="text-xs text-muted-foreground">
                      {new Date(reply.createdAt).toLocaleString()}
                    </span>
                  </div>
                  <p className="text-muted-foreground mt-0.5">{reply.body}</p>
                  <span className="flex items-center gap-1 text-xs text-muted-foreground mt-1">
                    <ArrowUp className="h-3 w-3" />
                    {reply.upvotes}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export default ForumPostDetail
