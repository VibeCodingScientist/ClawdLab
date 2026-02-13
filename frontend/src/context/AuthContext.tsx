/**
 * Authentication Context Provider
 *
 * Manages authentication state and provides auth-related functions
 * to the entire application.
 */

import {
  createContext,
  useCallback,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react'
import apiClient, {
  clearTokens,
  hasValidToken,
  setTokens,
} from '@/api/client'
import type { User, LoginCredentials, AuthTokens } from '@/types'
import { isMockMode } from '@/mock/useMockMode'

const MOCK_USER: User = {
  id: 'mock-user-001',
  username: 'demo',
  email: 'demo@sylva.ai',
  status: 'active',
  roles: ['user'],
  permissions: [],
  createdAt: new Date().toISOString(),
  updatedAt: new Date().toISOString(),
  loginCount: 0,
}

// ===========================================
// CONTEXT TYPES
// ===========================================

export interface AuthContextType {
  user: User | null
  isAuthenticated: boolean
  isLoading: boolean
  login: (credentials: LoginCredentials) => Promise<void>
  logout: () => Promise<void>
  refreshUser: () => Promise<void>
}

// ===========================================
// CONTEXT
// ===========================================

export const AuthContext = createContext<AuthContextType | null>(null)

// ===========================================
// PROVIDER
// ===========================================

interface AuthProviderProps {
  children: ReactNode
}

export function AuthProvider({ children }: AuthProviderProps) {
  const [user, setUser] = useState<User | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  const isAuthenticated = useMemo(() => !!user, [user])

  // Fetch current user from API
  const fetchUser = useCallback(async (): Promise<User | null> => {
    try {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const response = await apiClient.get<any>('/security/users/me')
      const raw = response.data
      return {
        id: raw.id,
        username: raw.username,
        email: raw.email,
        status: raw.status ?? 'active',
        roles: raw.roles ?? [],
        permissions: [],
        createdAt: raw.created_at ?? raw.createdAt ?? '',
        updatedAt: raw.updated_at ?? raw.updatedAt ?? '',
        loginCount: raw.login_count ?? raw.loginCount ?? 0,
        lastLogin: raw.last_login ?? raw.lastLogin,
      }
    } catch {
      return null
    }
  }, [])

  // Initialize auth state on mount
  useEffect(() => {
    const initAuth = async () => {
      if (isMockMode()) {
        setUser(MOCK_USER)
        setIsLoading(false)
        return
      }
      if (hasValidToken()) {
        const currentUser = await fetchUser()
        setUser(currentUser)
      }
      setIsLoading(false)
    }

    initAuth()
  }, [fetchUser])

  // Login function
  const login = useCallback(async (credentials: LoginCredentials) => {
    setIsLoading(true)
    try {
      // Authenticate with the API
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const response = await apiClient.post<{
        access_token: string
        refresh_token: string
        token_type: string
        expires_in: number
        user: any  // eslint-disable-line @typescript-eslint/no-explicit-any
      }>('/security/auth/login', {
        username: credentials.username,
        password: credentials.password,
      })

      const { access_token, refresh_token, token_type, expires_in, user: rawUser } = response.data

      // Store tokens
      const tokens: AuthTokens = {
        accessToken: access_token,
        refreshToken: refresh_token,
        tokenType: token_type,
        expiresIn: expires_in,
      }
      setTokens(tokens)

      // Map snake_case user to frontend User type
      const mappedUser: User = {
        id: rawUser.id,
        username: rawUser.username,
        email: rawUser.email,
        status: rawUser.status ?? 'active',
        roles: rawUser.roles ?? [],
        permissions: [],
        createdAt: rawUser.created_at ?? rawUser.createdAt ?? '',
        updatedAt: rawUser.updated_at ?? rawUser.updatedAt ?? '',
        loginCount: rawUser.login_count ?? rawUser.loginCount ?? 0,
        lastLogin: rawUser.last_login ?? rawUser.lastLogin,
      }
      setUser(mappedUser)
    } finally {
      setIsLoading(false)
    }
  }, [])

  // Logout function
  const logout = useCallback(async () => {
    setIsLoading(true)
    try {
      // Call logout endpoint to invalidate tokens on server
      await apiClient.post('/security/auth/logout')
    } catch {
      // Ignore errors during logout
    } finally {
      // Clear local state regardless of API response
      clearTokens()
      setUser(null)
      setIsLoading(false)
    }
  }, [])

  // Refresh user data
  const refreshUser = useCallback(async () => {
    if (hasValidToken()) {
      const currentUser = await fetchUser()
      setUser(currentUser)
    }
  }, [fetchUser])

  const value = useMemo(
    () => ({
      user,
      isAuthenticated,
      isLoading,
      login,
      logout,
      refreshUser,
    }),
    [user, isAuthenticated, isLoading, login, logout, refreshUser]
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
