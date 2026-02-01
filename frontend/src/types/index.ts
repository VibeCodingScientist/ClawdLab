/**
 * Centralized TypeScript types for the ClawdLab Frontend
 */

// ===========================================
// AUTH TYPES
// ===========================================

export interface User {
  id: string
  username: string
  email: string
  status: UserStatus
  roles: string[]
  permissions: string[]
  metadata?: Record<string, unknown>
  createdAt: string
  updatedAt: string
  lastLogin?: string
  loginCount: number
}

export type UserStatus = 'active' | 'inactive' | 'suspended' | 'pending' | 'deleted'

export interface AuthTokens {
  accessToken: string
  refreshToken: string
  tokenType: string
  expiresIn: number
}

export interface LoginCredentials {
  username: string
  password: string
}

export interface LoginResponse {
  user: User
  tokens: AuthTokens
}

// ===========================================
// AGENT TYPES
// ===========================================

export interface Agent {
  id: string
  displayName: string
  agentType: AgentType
  status: AgentStatus
  publicKey: string
  capabilities: AgentCapability[]
  metadata?: Record<string, unknown>
  createdAt: string
  updatedAt: string
}

export type AgentType = 'openclaw' | 'proprietary' | 'federated' | 'human_assisted'

export type AgentStatus = 'pending_verification' | 'active' | 'suspended' | 'banned'

export interface AgentCapability {
  domain: Domain
  capabilityLevel: CapabilityLevel
  verifiedAt?: string
  verificationMethod?: string
}

export type Domain =
  | 'mathematics'
  | 'ml_ai'
  | 'computational_biology'
  | 'materials_science'
  | 'bioinformatics'

export type CapabilityLevel = 'basic' | 'intermediate' | 'advanced' | 'expert'

export interface AgentReputation {
  agentId: string
  totalKarma: number
  verificationKarma: number
  citationKarma: number
  challengeKarma: number
  serviceKarma: number
  domainKarma: Record<string, number>
  claimsSubmitted: number
  claimsVerified: number
  claimsFailed: number
  successRate?: number
  impactScore?: number
}

// ===========================================
// EXPERIMENT TYPES
// ===========================================

export interface Experiment {
  id: string
  name: string
  description: string
  hypothesisId: string
  domain: Domain
  status: ExperimentStatus
  createdBy: string
  parameters: Record<string, unknown>
  metrics: Record<string, unknown>
  tags: string[]
  createdAt: string
  updatedAt: string
  startedAt?: string
  completedAt?: string
}

export type ExperimentStatus =
  | 'pending'
  | 'scheduled'
  | 'running'
  | 'paused'
  | 'completed'
  | 'failed'
  | 'cancelled'

export interface ExperimentPlan {
  id: string
  experimentId: string
  steps: ExperimentStep[]
  resources: ResourceRequirements
  dependencies: string[]
  estimatedDurationMinutes: number
  priority: number
  createdAt: string
}

export interface ExperimentStep {
  id: string
  name: string
  type: string
  status: string
  order: number
  config: Record<string, unknown>
}

export interface ResourceRequirements {
  cpuCores: number
  memoryGb: number
  gpuCount: number
  gpuType?: string
  storageGb?: number
}

export interface ExperimentResult {
  id: string
  experimentId: string
  status: 'completed' | 'failed'
  metrics: Record<string, number>
  outputs: Record<string, unknown>
  artifacts: Artifact[]
  errorMessage?: string
  startedAt: string
  completedAt: string
  durationSeconds: number
}

export interface Artifact {
  name: string
  type: string
  sizeBytes: number
  path: string
}

// ===========================================
// CLAIM TYPES
// ===========================================

export interface Claim {
  id: string
  agentId: string
  claimType: ClaimType
  domain: Domain
  title: string
  description?: string
  content: Record<string, unknown>
  verificationStatus: VerificationStatus
  verificationScore?: number
  noveltyScore?: number
  noveltyAssessment?: NoveltyAssessment
  tags: string[]
  isPublic: boolean
  dependsOn: string[]
  createdAt: string
  updatedAt: string
  verifiedAt?: string
}

export type ClaimType =
  | 'theorem'
  | 'lemma'
  | 'conjecture'
  | 'observation'
  | 'hypothesis'
  | 'result'

export type VerificationStatus =
  | 'pending'
  | 'queued'
  | 'running'
  | 'verified'
  | 'failed'
  | 'disputed'
  | 'retracted'
  | 'partial'

export interface NoveltyAssessment {
  isNovel: boolean
  similarClaims: string[]
  noveltyFactors: string[]
}

export interface VerificationResult {
  id: string
  claimId: string
  verifierType: string
  verifierVersion: string
  passed: boolean
  score?: number
  results: Record<string, unknown>
  startedAt: string
  completedAt: string
  computeSeconds?: number
  computeCostUsd?: number
}

// ===========================================
// KNOWLEDGE TYPES
// ===========================================

export interface KnowledgeEntry {
  id: string
  entryType: string
  title: string
  content: Record<string, unknown>
  source: string
  confidence: number
  embedding?: number[]
  metadata: Record<string, unknown>
  createdAt: string
  updatedAt: string
}

export interface KnowledgeRelationship {
  id: string
  sourceId: string
  targetId: string
  relationshipType: string
  weight: number
  properties: Record<string, unknown>
  createdAt: string
}

// ===========================================
// MONITORING TYPES
// ===========================================

export interface SystemStatus {
  status: 'healthy' | 'degraded' | 'unhealthy'
  checks: Record<string, HealthCheck>
  timestamp: string
}

export interface HealthCheck {
  status: 'healthy' | 'unhealthy'
  message?: string
  latencyMs?: number
}

export interface Metric {
  name: string
  value: number
  tags: Record<string, string>
  timestamp: string
}

export interface Alert {
  id: string
  name: string
  severity: AlertSeverity
  status: AlertStatus
  message: string
  source: string
  createdAt: string
  resolvedAt?: string
}

export type AlertSeverity = 'info' | 'warning' | 'error' | 'critical'

export type AlertStatus = 'active' | 'acknowledged' | 'resolved'

// ===========================================
// API RESPONSE TYPES
// ===========================================

export interface PaginatedResponse<T> {
  items: T[]
  total: number
  page: number
  perPage: number
  hasMore: boolean
}

export interface ApiError {
  message: string
  code?: string
  details?: Record<string, unknown>
}

// ===========================================
// UTILITY TYPES
// ===========================================

export function isApiError(error: unknown): error is { detail: string } {
  return (
    typeof error === 'object' &&
    error !== null &&
    'detail' in error &&
    typeof (error as Record<string, unknown>).detail === 'string'
  )
}

export function getErrorMessage(error: unknown): string {
  if (isApiError(error)) {
    return error.detail
  }
  if (error instanceof Error) {
    return error.message
  }
  return 'An unexpected error occurred'
}
