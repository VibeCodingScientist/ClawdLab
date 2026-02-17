/**
 * API client for user API key management
 */

import apiClient from '@/api/client'

export interface ApiKeyResponse {
  id: string
  name: string
  token_prefix: string
  scopes: string[]
  last_used_at: string | null
  created_at: string
  expires_at: string | null
}

export interface ApiKeyListResponse {
  items: ApiKeyResponse[]
  total: number
}

export interface ApiKeyCreateRequest {
  name: string
  scopes?: string[]
  expires_in_days?: number | null
}

export interface ApiKeyCreateResponse {
  id: string
  name: string
  token: string
  prefix: string
  scopes: string[]
  created_at: string
  expires_at: string | null
}

export async function fetchApiKeys(): Promise<ApiKeyListResponse> {
  const res = await apiClient.get('/user/api-keys')
  return res.data
}

export async function createApiKey(body: ApiKeyCreateRequest): Promise<ApiKeyCreateResponse> {
  const res = await apiClient.post('/user/api-keys', body)
  return res.data
}

export async function revokeApiKey(keyId: string): Promise<void> {
  await apiClient.delete(`/user/api-keys/${keyId}`)
}
