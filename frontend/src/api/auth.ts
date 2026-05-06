// v0.8 Phase D — Auth API client.
// Calls POST /api/auth/login, POST /api/auth/logout, GET /api/auth/me.
// The raw access_token is never logged or rendered; callers store it
// via setAuthToken() in client.ts (localStorage).

import { apiFetch, apiPost } from './client'
import type { LoginResponse, MeResponse } from './types'

export async function login(username: string, password: string): Promise<LoginResponse> {
  return apiPost<LoginResponse, { username: string; password: string }>(
    '/api/auth/login',
    { username, password },
  )
}

export async function logout(): Promise<void> {
  try {
    await apiPost<{ status: string }, Record<string, never>>('/api/auth/logout', {})
  } catch {
    // best-effort: server may return 401 on expired tokens
  }
}

export async function getMe(): Promise<MeResponse> {
  return apiFetch<MeResponse>('/api/auth/me')
}
