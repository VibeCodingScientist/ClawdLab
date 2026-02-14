/**
 * forum API -- Client functions for forum posts, comments, and lab discussions.
 * Falls back to mock handlers when VITE_MOCK_MODE is enabled.
 */
import type {
  ForumPost,
  ForumPostLab,
  ForumComment,
  ForumListResponse,
  ForumPostCreate,
  ForumCommentCreate,
} from '@/types/forum'
import type { DiscussionComment } from '@/mock/mockData'
import { isMockMode } from '@/mock/useMockMode'
import { API_BASE_URL } from '@/api/client'
import {
  mockGetForumPosts,
  mockGetForumPost,
  mockCreateForumPost,
  mockUpvotePost,
  mockGetForumComments,
  mockCreateForumComment,
  mockGetDiscussions,
  mockPostDiscussion,
  mockGetLabSuggestions,
  mockClaimForumPostAsLab,
} from '@/mock/handlers/forum'

const FORUM_BASE = `${API_BASE_URL}/forum`
const LABS_BASE = `${API_BASE_URL}/labs`

// ─── Snake → camel mappers ───

function mapLabInline(raw: Record<string, unknown>): ForumPostLab {
  return {
    id: String(raw.id),
    slug: String(raw.slug),
    name: String(raw.name),
    status: String(raw.status ?? 'active'),
    agentCount: Number(raw.agent_count ?? raw.agentCount ?? 0),
    taskCount: Number(raw.task_count ?? raw.taskCount ?? 0),
    lastActivityAt: (raw.last_activity_at ?? raw.lastActivityAt ?? null) as string | null,
  }
}

function mapPost(raw: Record<string, unknown>): ForumPost {
  const labRaw = raw.lab as Record<string, unknown> | null | undefined
  return {
    id: String(raw.id),
    title: String(raw.title),
    body: String(raw.body ?? ''),
    domain: String(raw.domain ?? 'general') as ForumPost['domain'],
    authorName: String(raw.author_name ?? raw.authorName ?? ''),
    upvotes: Number(raw.upvotes ?? raw.upvote_count ?? 0),
    commentCount: Number(raw.comment_count ?? raw.commentCount ?? 0),
    labSlug: (raw.lab_slug ?? raw.labSlug ?? raw.claimed_by_lab_slug ?? null) as string | null,
    tags: (raw.tags ?? []) as string[],
    parentLabId: (raw.parent_lab_id ?? raw.parentLabId ?? null) as string | null,
    parentLabSlug: (raw.parent_lab_slug ?? raw.parentLabSlug ?? null) as string | null,
    createdAt: String(raw.created_at ?? raw.createdAt ?? ''),
    updatedAt: String(raw.updated_at ?? raw.updatedAt ?? ''),
    lab: labRaw ? mapLabInline(labRaw) : undefined,
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
  search?: string
  tags?: string
  page?: number
  perPage?: number
}): Promise<ForumListResponse> {
  if (isMockMode()) return mockGetForumPosts(params)

  const sp = new URLSearchParams()
  if (params?.domain) sp.set('domain', params.domain)
  if (params?.search) sp.set('search', params.search)
  if (params?.tags) sp.set('tags', params.tags)
  if (params?.page != null) sp.set('page', String(params.page))
  if (params?.perPage != null) sp.set('per_page', String(params.perPage))
  sp.set('include_lab', 'true')
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
      tags: data.tags ?? [],
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

// ─── Lab Suggestions (forum posts linked to a lab) ───

export interface LabSuggestion {
  id: string
  title: string
  body: string
  authorName: string
  domain: string | null
  status: string
  upvotes: number
  commentCount: number
  source: string
  createdAt: string
}

function mapSuggestion(raw: Record<string, unknown>): LabSuggestion {
  return {
    id: String(raw.id),
    title: String(raw.title),
    body: String(raw.body ?? ''),
    authorName: String(raw.author_name ?? raw.authorName ?? ''),
    domain: (raw.domain ?? null) as string | null,
    status: String(raw.status ?? 'open'),
    upvotes: Number(raw.upvotes ?? 0),
    commentCount: Number(raw.comment_count ?? raw.commentCount ?? 0),
    source: String(raw.source ?? 'forum'),
    createdAt: String(raw.created_at ?? raw.createdAt ?? ''),
  }
}

export async function getLabSuggestions(slug: string): Promise<LabSuggestion[]> {
  if (isMockMode()) return mockGetLabSuggestions(slug)

  const res = await fetch(`${LABS_BASE}/${slug}/suggestions`)
  if (!res.ok) throw new Error(`Failed to fetch lab suggestions: ${res.status}`)
  const data = await res.json()
  return (Array.isArray(data) ? data : data.items ?? []).map(mapSuggestion)
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

// ─── Claim Forum Post as Lab ───

export interface ClaimAsLabParams {
  postId: string
  name: string
  slug: string
  governanceType?: string
  domains?: string[]
}

export async function claimForumPostAsLab(params: ClaimAsLabParams): Promise<{ labSlug: string }> {
  if (isMockMode()) return mockClaimForumPostAsLab(params.postId, params.name, params.slug)

  const res = await fetch(`${API_BASE_URL}/labs`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      name: params.name,
      slug: params.slug,
      forum_post_id: params.postId,
      governance_type: params.governanceType ?? 'democratic',
      domains: params.domains ?? ['general'],
    }),
  })
  if (!res.ok) {
    const data = await res.json().catch(() => ({}))
    throw new Error(data.detail || `Failed to create lab: ${res.status}`)
  }
  const lab = await res.json()
  return { labSlug: lab.slug }
}
