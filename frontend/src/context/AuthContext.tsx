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
  getAccessToken,
  hasValidToken,
  setTokens,
} from '@/api/client'
import type { User, LoginCredentials, AuthTokens } from '@/types'

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
      const response = await apiClient.get<User>('/security/users/me')
      return response.data
    } catch {
      return null
    }
  }, [])

  // Initialize auth state on mount
  useEffect(() => {
    const initAuth = async () => {
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
      const response = await apiClient.post<{
        access_token: string
        refresh_token: string
        token_type: string
        expires_in: number
        user: User
      }>('/security/auth/login', {
        username: credentials.username,
        password: credentials.password,
      })

      const { access_token, refresh_token, token_type, expires_in, user: userData } = response.data

      // Store tokens
      const tokens: AuthTokens = {
        accessToken: access_token,
        refreshToken: refresh_token,
        tokenType: token_type,
        expiresIn: expires_in,
      }
      setTokens(tokens)

      // Set user state
      setUser(userData)
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
