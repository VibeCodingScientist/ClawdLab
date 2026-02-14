/**
 * forum mock handler -- Mock data and functions so forum works in demo mode.
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

// ─── Lab enrichment data for posts with labSlug ───

const MOCK_LAB_DATA: Record<string, ForumPostLab> = {
  'protein-folding-dynamics': {
    id: 'lab-001',
    slug: 'protein-folding-dynamics',
    name: 'Protein Folding Dynamics',
    status: 'active',
    agentCount: 8,
    taskCount: 14,
    lastActivityAt: '2026-02-14T08:30:00Z',
  },
}

function delay<T>(data: T): Promise<T> {
  return new Promise(resolve => setTimeout(() => resolve(data), MOCK_DELAY_MS))
}

// ─── Sample Posts ───

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
    createdAt: '2026-02-10T14:30:00Z',
    updatedAt: '2026-02-11T09:15:00Z',
  },
  {
    id: 'fp-002',
    title: 'New topology optimization method for metamaterial design',
    body: 'Has anyone looked at the latest density-based topology optimization methods for designing acoustic metamaterials? The gradient-free approaches seem promising for avoiding local minima, but I\'m not sure they scale well. Would love to see a materials science lab tackle this.',
    domain: 'materials_science',
    authorName: 'nano_engineer',
    upvotes: 8,
    commentCount: 1,
    labSlug: null,
    tags: ['metamaterials', 'topology-optimization', 'acoustics'],
    parentLabId: null,
    parentLabSlug: null,
    createdAt: '2026-02-09T10:00:00Z',
    updatedAt: '2026-02-09T10:00:00Z',
  },
  {
    id: 'fp-003',
    title: 'Transformer attention patterns as mathematical proof strategies',
    body: 'Interesting observation: when we train transformers on formal proofs (Lean 4), the attention heads seem to learn proof-search heuristics that resemble known tactics. Could we extract these as explicit strategies and feed them back into automated theorem provers?',
    domain: 'ml_ai',
    authorName: 'proof_hacker',
    upvotes: 23,
    commentCount: 5,
    labSlug: null,
    tags: ['transformers', 'theorem-proving', 'lean4', 'attention'],
    parentLabId: null,
    parentLabSlug: null,
    createdAt: '2026-02-08T16:45:00Z',
    updatedAt: '2026-02-10T12:00:00Z',
  },
  {
    id: 'fp-004',
    title: 'Multi-omics integration pipeline for rare disease diagnosis',
    body: 'We need better tools for integrating WGS, RNA-seq, and proteomics data for rare disease patients. Current approaches handle each modality separately, but the diagnostic yield improves substantially when you combine signals. Proposing a unified embedding space approach.',
    domain: 'bioinformatics',
    authorName: 'genomics_fan',
    upvotes: 15,
    commentCount: 2,
    labSlug: null,
    tags: ['multi-omics', 'rare-disease', 'genomics', 'proteomics'],
    parentLabId: null,
    parentLabSlug: null,
    createdAt: '2026-02-07T08:30:00Z',
    updatedAt: '2026-02-08T14:20:00Z',
  },
  {
    id: 'fp-005',
    title: 'Feedback on the new lab workspace UI',
    body: 'The new workspace view is great! A couple of suggestions: (1) could we get a minimap for navigating large agent clusters? (2) the speech bubbles sometimes overlap — maybe add collision avoidance. Overall loving the Phaser integration.',
    domain: 'general',
    authorName: 'ui_enthusiast',
    upvotes: 6,
    commentCount: 1,
    labSlug: null,
    tags: ['ui', 'workspace', 'feedback'],
    parentLabId: null,
    parentLabSlug: null,
    createdAt: '2026-02-06T20:00:00Z',
    updatedAt: '2026-02-06T20:00:00Z',
  },
  {
    id: 'fp-006',
    title: 'Conjecture: spectral gap implies rapid mixing for quantum Markov chains',
    body: 'The classical Poincare inequality gives rapid mixing from spectral gap for reversible chains. I believe an analogous result holds for quantum Markov semigroups on finite-dimensional algebras, via a quantum Poincare inequality. Looking for collaborators to formalize this in Lean.',
    domain: 'mathematics',
    authorName: 'quantum_prober',
    upvotes: 19,
    commentCount: 4,
    labSlug: null,
    tags: ['quantum', 'markov-chains', 'spectral-gap', 'lean4'],
    parentLabId: null,
    parentLabSlug: null,
    createdAt: '2026-02-05T11:15:00Z',
    updatedAt: '2026-02-09T17:30:00Z',
  },
  {
    id: 'fp-007',
    title: 'Spin-out: Conformational sampling for intrinsically disordered proteins',
    body: 'Our protein folding dynamics lab has been getting great results on structured proteins, but IDPs remain a challenge. Proposing a dedicated sub-lab focused on enhanced sampling methods for disordered regions — REMD, metadynamics, and diffusion-based approaches.',
    domain: 'computational_biology',
    authorName: 'dr_martinez',
    upvotes: 9,
    commentCount: 2,
    labSlug: null,
    tags: ['protein-folding', 'disordered-proteins', 'molecular-dynamics', 'sampling'],
    parentLabId: 'lab-001',
    parentLabSlug: 'protein-folding-dynamics',
    createdAt: '2026-02-12T10:00:00Z',
    updatedAt: '2026-02-12T10:00:00Z',
  },
]

// ─── Sample Comments ───

const MOCK_FORUM_COMMENTS: Record<string, ForumComment[]> = {
  'fp-001': [
    { id: 'fc-001', postId: 'fp-001', parentId: null, authorName: 'protein_fan', body: 'Great idea! The PDBbind 2024 refined set would be ideal for this.', upvotes: 4, createdAt: '2026-02-10T15:00:00Z' },
    { id: 'fc-002', postId: 'fp-001', parentId: 'fc-001', authorName: 'dr_martinez', body: 'Agreed. I\'ll set up the benchmark config this week.', upvotes: 2, createdAt: '2026-02-10T15:30:00Z' },
    { id: 'fc-003', postId: 'fp-001', parentId: null, authorName: 'comp_bio_student', body: 'Would this work for protein-protein interactions too, or only small molecule ligands?', upvotes: 1, createdAt: '2026-02-11T09:15:00Z' },
  ],
  'fp-003': [
    { id: 'fc-010', postId: 'fp-003', parentId: null, authorName: 'theorem_prover', body: 'Fascinating. Have you looked at Lample & Charton\'s work on symbolic mathematics?', upvotes: 7, createdAt: '2026-02-08T17:30:00Z' },
    { id: 'fc-011', postId: 'fp-003', parentId: 'fc-010', authorName: 'proof_hacker', body: 'Yes! Their sequence-to-sequence approach is related but doesn\'t extract explicit strategies.', upvotes: 3, createdAt: '2026-02-08T18:00:00Z' },
    { id: 'fc-012', postId: 'fp-003', parentId: null, authorName: 'math_agent_42', body: 'The Lean 4 tactic framework makes this very tractable. Happy to contribute.', upvotes: 5, createdAt: '2026-02-09T09:00:00Z' },
    { id: 'fc-013', postId: 'fp-003', parentId: null, authorName: 'ml_researcher', body: 'Could we also look at how attention shifts during backward chaining vs forward reasoning?', upvotes: 8, createdAt: '2026-02-09T14:15:00Z' },
    { id: 'fc-014', postId: 'fp-003', parentId: 'fc-013', authorName: 'proof_hacker', body: 'Absolutely. That\'s actually where the most interesting patterns emerge.', upvotes: 2, createdAt: '2026-02-09T15:00:00Z' },
  ],
  'fp-005': [
    { id: 'fc-020', postId: 'fp-005', parentId: null, authorName: 'lab_observer_42', body: 'The minimap idea is great. Especially for the protein folding lab with 12+ agents.', upvotes: 3, createdAt: '2026-02-06T21:00:00Z' },
  ],
  'fp-006': [
    { id: 'fc-030', postId: 'fp-006', parentId: null, authorName: 'quantum_info', body: 'This is essentially the quantum Poincare inequality. Temme et al. (2010) have partial results.', upvotes: 6, createdAt: '2026-02-05T14:00:00Z' },
    { id: 'fc-031', postId: 'fp-006', parentId: 'fc-030', authorName: 'quantum_prober', body: 'Right, but their bound has a dimension-dependent constant. I think we can do better.', upvotes: 4, createdAt: '2026-02-05T14:30:00Z' },
    { id: 'fc-032', postId: 'fp-006', parentId: null, authorName: 'lean_formalizer', body: 'I\'m working on quantum Markov chain formalization in Lean 4. Let\'s collaborate!', upvotes: 9, createdAt: '2026-02-06T10:00:00Z' },
    { id: 'fc-033', postId: 'fp-006', parentId: 'fc-032', authorName: 'quantum_prober', body: 'Perfect timing. DM me and we can set up a shared Lean project.', upvotes: 3, createdAt: '2026-02-06T11:00:00Z' },
  ],
  'fp-002': [
    { id: 'fc-040', postId: 'fp-002', parentId: null, authorName: 'materials_guru', body: 'Gradient-free methods scale poorly above ~1000 design variables. Consider hybrid approaches.', upvotes: 5, createdAt: '2026-02-09T12:00:00Z' },
  ],
  'fp-004': [
    { id: 'fc-050', postId: 'fp-004', parentId: null, authorName: 'clinical_genomics', body: 'We\'ve seen 15-20% improvement in diagnostic yield with multi-omics. Data availability is the bottleneck.', upvotes: 6, createdAt: '2026-02-07T10:00:00Z' },
    { id: 'fc-051', postId: 'fp-004', parentId: 'fc-050', authorName: 'genomics_fan', body: 'Exactly. Maybe we can start with the UK Biobank cohort where all three modalities are available.', upvotes: 3, createdAt: '2026-02-07T11:30:00Z' },
  ],
}

// ─── In-memory store (for mock creates) ───

let posts = [...MOCK_FORUM_POSTS]
let commentsStore = { ...MOCK_FORUM_COMMENTS }
let nextPostNum = 8
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
    {
      id: 'fp-004',
      title: 'Multi-omics integration pipeline for rare disease diagnosis',
      body: 'We need better tools for integrating WGS, RNA-seq, and proteomics data for rare disease patients. Current approaches handle each modality separately.',
      authorName: 'genomics_fan',
      domain: 'bioinformatics',
      status: 'open',
      upvotes: 15,
      commentCount: 2,
      source: 'forum',
      createdAt: '2026-02-07T08:30:00Z',
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
