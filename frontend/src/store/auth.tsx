// v0.8 Phase D — Auth context + hook.
// AuthProvider calls GET /api/auth/me on mount to determine whether
// AUTH_ENABLED=true on the server and who the current user is.
// When AUTH_ENABLED=false (dev/CI default) isAuthenticated is set to true
// immediately — the dev fallback identity bypasses token checks.
//
// The raw access_token is NEVER rendered to the DOM or stored in component
// state — only setAuthToken() / getAuthToken() touch localStorage directly.

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
} from 'react'
import type { ReactNode } from 'react'
import { getMe, logout as logoutApi } from '@/api/auth'
import { getAuthToken, removeAuthToken, setAuthToken } from '@/api/client'
import type { LoginResponse, LoginUser } from '@/api/types'

interface AuthState {
  isAuthenticated: boolean
  authEnabled: boolean
  currentUser: LoginUser | null
  isLoading: boolean
}

interface AuthContextValue extends AuthState {
  onLoginSuccess: (response: LoginResponse) => void
  logout: () => void
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>({
    isAuthenticated: false,
    authEnabled: false,
    currentUser: null,
    isLoading: true,
  })

  useEffect(() => {
    getMe()
      .then(me => {
        if (!me.auth_enabled) {
          setState({
            isAuthenticated: true,
            authEnabled: false,
            currentUser: me.user,
            isLoading: false,
          })
        } else {
          const token = getAuthToken()
          setState({
            isAuthenticated: !!token && me.user !== null,
            authEnabled: true,
            currentUser: me.user,
            isLoading: false,
          })
        }
      })
      .catch(() => {
        setState(prev => ({ ...prev, isLoading: false }))
      })
  }, [])

  const onLoginSuccess = useCallback((response: LoginResponse) => {
    setAuthToken(response.access_token)
    setState({
      isAuthenticated: true,
      authEnabled: true,
      currentUser: response.user,
      isLoading: false,
    })
  }, [])

  const logout = useCallback(() => {
    void logoutApi()
    removeAuthToken()
    setState(prev => ({
      ...prev,
      isAuthenticated: false,
      currentUser: null,
    }))
  }, [])

  return (
    <AuthContext.Provider value={{ ...state, onLoginSuccess, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
