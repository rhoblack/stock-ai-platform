// v0.9 Phase D — UserPreference API client.
//
// Endpoints:
//   GET /api/users/me/preferences  — fetch (or lazily create) preferences
//   PUT /api/users/me/preferences  — replace all preference fields
//
// Policy:
//   - user_id is NEVER sent in the request body (server uses token claim)
//   - notification_preferences_json: UI-only on/off flags, no live send
//   - Forbidden fields (password, token, secret, broker, account, quantity,
//     order_*, source_file_path) are never included in payload or rendered

import { apiFetch, apiPut } from './client'
import type { UserPreference, UserPreferenceUpdateRequest } from './types'

export function getMyPreferences(): Promise<UserPreference> {
  return apiFetch<UserPreference>('/api/users/me/preferences')
}

export function updateMyPreferences(
  payload: UserPreferenceUpdateRequest,
): Promise<UserPreference> {
  return apiPut<UserPreference, UserPreferenceUpdateRequest>(
    '/api/users/me/preferences',
    payload,
  )
}
