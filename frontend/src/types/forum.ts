/**
 * forum types -- TypeScript interfaces for forum posts, comments, and domains.
 */

export type ForumDomain =
  | 'computational_biology'
  | 'mathematics'
  | 'ml_ai'
  | 'materials_science'
  | 'bioinformatics'
  | 'general'

export interface ForumPostLab {
  id: string
  slug: string
  name: string
  status: string
  agentCount: number
  taskCount: number
  tasksCompleted: number
  tasksAccepted: number
  tasksInProgress: number
  lastActivityAt: string | null
  activeLabStateTitle: string | null
}

export interface ForumPost {
  id: string
  title: string
  body: string
  domain: ForumDomain
  authorName: string
  upvotes: number
  commentCount: number
  labSlug: string | null
  tags: string[]
  parentLabId: string | null
  parentLabSlug: string | null
  createdAt: string
  updatedAt: string
  lab?: ForumPostLab | null
  /** True only for built-in sample data shown in demo/mock mode */
  isSample?: boolean
}

export interface ForumComment {
  id: string
  postId: string
  parentId: string | null
  authorName: string
  body: string
  upvotes: number
  createdAt: string
}

export interface ForumPostCreate {
  title: string
  body: string
  domain: ForumDomain
  authorName: string
  labSlug?: string
  tags?: string[]
}

export interface ForumCommentCreate {
  authorName: string
  body: string
  parentId?: string
}

export interface ForumListResponse {
  items: ForumPost[]
  total: number
  page: number
  perPage: number
}
