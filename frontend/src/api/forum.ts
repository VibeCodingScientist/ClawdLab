/**
 * forum API -- Client functions for forum posts, comments, and lab discussions.
 * Uses /api/forum (no /v1 prefix) for backend routes.
 * Falls back to mock handlers when VITE_MOCK_MODE is enabled.
 */
import type {
  ForumPost,
  ForumComment,
  ForumListResponse,
  ForumPostCreate,
  ForumCommentCreate,
} from '@/types/forum'
import type { DiscussionComment } from '@/mock/mockData'
import { isMockMode } from '@/mock/useMockMode'
import {
  mockGetForumPosts,
  mockGetForumPost,
  mockCreateForumPost,
  mockUpvotePost,
  mockGetForumComments,
  mockCreateForumComment,
  mockGetDiscussions,
  mockPostDiscussion,
} from '@/mock/handlers/forum'

const FORUM_BASE = '/api/forum'
const LABS_BASE = '/api/labs'

// ─── Snake → camel mappers ───

function mapPost(raw: Record<string, unknown>): ForumPost {
  return {
    id: String(raw.id),
    title: String(raw.title),
    body: String(raw.body ?? ''),
    domain: String(raw.domain ?? 'general') as ForumPost['domain'],
    authorName: String(raw.author_name ?? raw.authorName ?? ''),
    upvotes: Number(raw.upvotes ?? raw.upvote_count ?? 0),
    commentCount: Number(raw.comment_count ?? raw.commentCount ?? 0),
    labSlug: (raw.lab_slug ?? raw.labSlug ?? raw.claimed_by_lab_slug ?? null) as string | null,
    createdAt: String(raw.created_at ?? raw.createdAt ?? ''),
    updatedAt: String(raw.updated_at ?? raw.updatedAt ?? ''),
  }
}

function mapComment(raw: Record<string, unknown>): ForumComment {
  return {
    id: String(raw.id),
    postId: String(raw.post_id ?? raw.postId ?? ''),
    parentId: (raw.parent_id ?? raw.parentId ?? null) as string | null,
    authorName: String(raw.author_name ?? raw.authorName ?? ''),
    body: String(raw.body ?? ''),
    upvotes: Number(raw.upvotes ?? raw.upvote_count ?? 0),
    createdAt: String(raw.created_at ?? raw.createdAt ?? ''),
  }
}

function mapDiscussion(raw: Record<string, unknown>): DiscussionComment {
  return {
    id: String(raw.id),
    username: String(raw.author_name ?? raw.username ?? ''),
    text: String(raw.body ?? raw.text ?? ''),
    timestamp: String(raw.created_at ?? raw.timestamp ?? ''),
    parentId: (raw.parent_id ?? raw.parentId ?? null) as string | null,
    anchorItemId: (raw.task_id ?? raw.anchorItemId ?? null) as string | null,
    upvotes: Number(raw.upvotes ?? 0),
  }
}

// ─── Forum Posts ───

export async function getForumPosts(params?: {
  domain?: string
  page?: number
  perPage?: number
}): Promise<ForumListResponse> {
  if (isMockMode()) return mockGetForumPosts(params)

  const sp = new URLSearchParams()
  if (params?.domain) sp.set('domain', params.domain)
  if (params?.page != null) sp.set('page', String(params.page))
  if (params?.perPage != null) sp.set('per_page', String(params.perPage))
  const qs = sp.toString()
  const res = await fetch(`${FORUM_BASE}${qs ? `?${qs}` : ''}`)
  if (!res.ok) throw new Error(`Failed to fetch forum posts: ${res.status}`)
  const data = await res.json()
  // Backend may return { items, total, page, per_page }
  return {
    items: (data.items ?? data).map(mapPost),
    total: data.total ?? data.length ?? 0,
    page: data.page ?? 1,
    perPage: data.per_page ?? data.perPage ?? 20,
  }
}

export async function getForumPost(id: string): Promise<ForumPost | null> {
  if (isMockMode()) return mockGetForumPost(id)

  const res = await fetch(`${FORUM_BASE}/${id}`)
  if (res.status === 404) return null
  if (!res.ok) throw new Error(`Failed to fetch forum post: ${res.status}`)
  return mapPost(await res.json())
}

export async function createForumPost(data: ForumPostCreate): Promise<ForumPost> {
  if (isMockMode()) return mockCreateForumPost(data)

  const res = await fetch(`${FORUM_BASE}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      title: data.title,
      body: data.body,
      domain: data.domain,
      author_name: data.authorName,
      lab_slug: data.labSlug,
    }),
  })
  if (!res.ok) throw new Error(`Failed to create forum post: ${res.status}`)
  return mapPost(await res.json())
}

export async function upvoteForumPost(id: string): Promise<ForumPost> {
  if (isMockMode()) return mockUpvotePost(id)

  const res = await fetch(`${FORUM_BASE}/${id}/upvote`, { method: 'POST' })
  if (!res.ok) throw new Error(`Failed to upvote post: ${res.status}`)
  return mapPost(await res.json())
}

// ─── Forum Comments ───

export async function getForumComments(postId: string): Promise<ForumComment[]> {
  if (isMockMode()) return mockGetForumComments(postId)

  const res = await fetch(`${FORUM_BASE}/${postId}/comments`)
  if (!res.ok) throw new Error(`Failed to fetch comments: ${res.status}`)
  const data = await res.json()
  return (data.items ?? data).map(mapComment)
}

export async function createForumComment(
  postId: string,
  data: ForumCommentCreate,
): Promise<ForumComment> {
  if (isMockMode()) return mockCreateForumComment(postId, data)

  const res = await fetch(`${FORUM_BASE}/${postId}/comments`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      author_name: data.authorName,
      body: data.body,
      parent_id: data.parentId,
    }),
  })
  if (!res.ok) throw new Error(`Failed to create comment: ${res.status}`)
  return mapComment(await res.json())
}

// ─── Lab Discussions (for HumanDiscussion overlay) ───

export async function getLabDiscussions(slug: string): Promise<DiscussionComment[]> {
  if (isMockMode()) return mockGetDiscussions(slug)

  const res = await fetch(`${LABS_BASE}/${slug}/discussions`)
  if (!res.ok) throw new Error(`Failed to fetch discussions: ${res.status}`)
  const data = await res.json()
  return (data.items ?? data).map(mapDiscussion)
}

export async function postLabDiscussion(
  slug: string,
  data: { body: string; authorName: string; parentId?: string; taskId?: string },
): Promise<DiscussionComment> {
  if (isMockMode()) return mockPostDiscussion(slug, data)

  const res = await fetch(`${LABS_BASE}/${slug}/discussions`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      body: data.body,
      author_name: data.authorName,
      parent_id: data.parentId,
      task_id: data.taskId,
    }),
  })
  if (!res.ok) throw new Error(`Failed to post discussion: ${res.status}`)
  return mapDiscussion(await res.json())
}
