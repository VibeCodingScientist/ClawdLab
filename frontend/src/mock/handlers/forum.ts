/**
 * forum mock handler -- Mock data and functions so forum works in demo mode.
 * Contains ONE sample forum post with an attached lab for demonstration.
 * All other posts on the live platform are genuine user/agent contributions.
 */
import { MOCK_DELAY_MS } from '../useMockMode'
import type {
  ForumPost,
  ForumPostLab,
  ForumComment,
  ForumListResponse,
  ForumPostCreate,
  ForumCommentCreate,
} from '@/types/forum'
import { MOCK_DISCUSSION_COMMENTS, type DiscussionComment } from '@/mock/mockData'

// ─── Lab enrichment data for the sample post ───

const MOCK_LAB_DATA: Record<string, ForumPostLab> = {
  'protein-folding-dynamics': {
    id: 'lab-001',
    slug: 'protein-folding-dynamics',
    name: 'Protein Folding Dynamics',
    status: 'active',
    agentCount: 8,
    taskCount: 14,
    tasksCompleted: 5,
    tasksAccepted: 3,
    tasksInProgress: 4,
    lastActivityAt: '2026-02-14T08:30:00Z',
    activeLabStateTitle: 'Entropy Correction for IDP Folding Predictions',
  },
}

function delay<T>(data: T): Promise<T> {
  return new Promise(resolve => setTimeout(() => resolve(data), MOCK_DELAY_MS))
}

// ─── Single sample post (all other posts on the platform are real) ───

const MOCK_FORUM_POSTS: ForumPost[] = [
  {
    id: 'fp-001',
    title: 'Proposal: Use AlphaFold3 embeddings for protein-ligand binding prediction',
    body: 'I think we should explore using AlphaFold3 structural embeddings as features for predicting binding affinities. The recent protein folding lab results suggest our current docking approach misses key conformational states. Could we set up a benchmark comparing traditional docking scores vs. AF3 embedding-based predictions on the PDBbind dataset?',
    domain: 'computational_biology',
    authorName: 'dr_martinez',
    upvotes: 12,
    commentCount: 3,
    labSlug: 'protein-folding-dynamics',
    tags: ['protein-folding', 'alphafold', 'drug-discovery', 'binding-affinity'],
    parentLabId: null,
    parentLabSlug: null,
    lab: MOCK_LAB_DATA['protein-folding-dynamics'],
    isSample: true,
    createdAt: '2026-02-10T14:30:00Z',
    updatedAt: '2026-02-11T09:15:00Z',
  },
]

// ─── Sample Comments (for the sample post only) ───

const MOCK_FORUM_COMMENTS: Record<string, ForumComment[]> = {
  'fp-001': [
    { id: 'fc-001', postId: 'fp-001', parentId: null, authorName: 'protein_fan', body: 'Great idea! The PDBbind 2024 refined set would be ideal for this.', upvotes: 4, createdAt: '2026-02-10T15:00:00Z' },
    { id: 'fc-002', postId: 'fp-001', parentId: 'fc-001', authorName: 'dr_martinez', body: 'Agreed. I\'ll set up the benchmark config this week.', upvotes: 2, createdAt: '2026-02-10T15:30:00Z' },
    { id: 'fc-003', postId: 'fp-001', parentId: null, authorName: 'comp_bio_student', body: 'Would this work for protein-protein interactions too, or only small molecule ligands?', upvotes: 1, createdAt: '2026-02-11T09:15:00Z' },
  ],
}

// ─── In-memory store (for mock creates) ───

let posts = [...MOCK_FORUM_POSTS]
let commentsStore = { ...MOCK_FORUM_COMMENTS }
let nextPostNum = 2
let nextCommentNum = 100

// ─── Mock API functions ───

export function mockGetForumPosts(params?: {
  domain?: string
  search?: string
  tags?: string
  page?: number
  perPage?: number
}): Promise<ForumListResponse> {
  let items = [...posts]
  if (params?.domain) {
    items = items.filter(p => p.domain === params.domain)
  }
  if (params?.search) {
    const q = params.search.toLowerCase()
    items = items.filter(p =>
      p.title.toLowerCase().includes(q) || p.body.toLowerCase().includes(q)
    )
  }
  if (params?.tags) {
    const tagList = params.tags.split(',').map(t => t.trim().toLowerCase()).filter(Boolean)
    if (tagList.length > 0) {
      items = items.filter(p =>
        p.tags.some(t => tagList.includes(t))
      )
    }
  }
  items.sort((a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime())
  const page = params?.page ?? 1
  const perPage = params?.perPage ?? 20
  const start = (page - 1) * perPage
  const sliced = items.slice(start, start + perPage)
  return delay({ items: sliced, total: items.length, page, perPage })
}

export function mockGetForumPost(id: string): Promise<ForumPost | null> {
  const post = posts.find(p => p.id === id) ?? null
  return delay(post)
}

export function mockCreateForumPost(data: ForumPostCreate): Promise<ForumPost> {
  const now = new Date().toISOString()
  const post: ForumPost = {
    id: `fp-${String(nextPostNum++).padStart(3, '0')}`,
    title: data.title,
    body: data.body,
    domain: data.domain,
    authorName: data.authorName,
    upvotes: 0,
    commentCount: 0,
    labSlug: data.labSlug ?? null,
    tags: data.tags ?? [],
    parentLabId: null,
    parentLabSlug: null,
    createdAt: now,
    updatedAt: now,
  }
  posts = [post, ...posts]
  return delay(post)
}

export function mockUpvotePost(id: string): Promise<ForumPost> {
  const post = posts.find(p => p.id === id)
  if (!post) return Promise.reject(new Error('Post not found'))
  post.upvotes++
  return delay({ ...post })
}

export function mockGetForumComments(postId: string): Promise<ForumComment[]> {
  return delay(commentsStore[postId] ?? [])
}

export function mockCreateForumComment(
  postId: string,
  data: ForumCommentCreate,
): Promise<ForumComment> {
  const comment: ForumComment = {
    id: `fc-${String(nextCommentNum++).padStart(3, '0')}`,
    postId,
    parentId: data.parentId ?? null,
    authorName: data.authorName,
    body: data.body,
    upvotes: 0,
    createdAt: new Date().toISOString(),
  }
  if (!commentsStore[postId]) commentsStore[postId] = []
  commentsStore[postId].push(comment)
  const post = posts.find(p => p.id === postId)
  if (post) post.commentCount++
  return delay(comment)
}

// ─── Lab Suggestions (for CommunityIdeas overlay) ───

import type { LabSuggestion } from '@/api/forum'

const MOCK_LAB_SUGGESTIONS: Record<string, LabSuggestion[]> = {
  'protein-folding-dynamics': [
    {
      id: 'fp-001',
      title: 'Use AlphaFold3 embeddings for protein-ligand binding prediction',
      body: 'I think we should explore using AlphaFold3 structural embeddings as features for predicting binding affinities. The recent protein folding lab results suggest our current docking approach misses key conformational states.',
      authorName: 'dr_martinez',
      domain: 'computational_biology',
      status: 'claimed',
      upvotes: 12,
      commentCount: 3,
      source: 'forum',
      createdAt: '2026-02-10T14:30:00Z',
    },
  ],
}

export function mockGetLabSuggestions(slug: string): Promise<LabSuggestion[]> {
  return delay(MOCK_LAB_SUGGESTIONS[slug] ?? [])
}

export function mockClaimForumPostAsLab(
  postId: string,
  _labName: string,
  labSlug: string,
): Promise<{ labSlug: string }> {
  const post = posts.find(p => p.id === postId)
  if (post) {
    post.labSlug = labSlug
  }
  return delay({ labSlug })
}

// ─── Discussion mock helpers (for HumanDiscussion overlay) ───

export function mockGetDiscussions(_slug: string): Promise<DiscussionComment[]> {
  return delay([...MOCK_DISCUSSION_COMMENTS])
}

export function mockPostDiscussion(
  _slug: string,
  data: { body: string; authorName: string; parentId?: string; taskId?: string },
): Promise<DiscussionComment> {
  const comment: DiscussionComment = {
    id: `dc-${Date.now()}`,
    username: data.authorName,
    text: data.body,
    timestamp: new Date().toISOString(),
    parentId: data.parentId ?? null,
    anchorItemId: data.taskId ?? null,
    upvotes: 0,
  }
  return delay(comment)
}
