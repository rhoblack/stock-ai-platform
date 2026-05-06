// v0.9 Phase D — UserPreference React Query hooks.
//
// Queries:  useUserPreferences
// Mutations: useUpdateUserPreferences
// Derived:  useEffectiveDefaultWatchlistId
//   — returns preference.default_watchlist_id if set,
//     otherwise falls back to the watchlist list's default/first entry.
//     This keeps TodayReport and FavoriteButton working before the user
//     has ever touched Settings.

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { getMyPreferences, updateMyPreferences } from '@/api/preferences'
import { useDefaultWatchlistId } from './useWatchlists'
import type { UserPreferenceUpdateRequest } from '@/api/types'

// ---------------------------------------------------------------------------
// Query: fetch user preferences (lazy-creates server-side on first call)
// ---------------------------------------------------------------------------

export function useUserPreferences() {
  return useQuery({
    queryKey: ['userPreferences'],
    queryFn: getMyPreferences,
    staleTime: 60_000,
  })
}

// ---------------------------------------------------------------------------
// Mutation: replace all preference fields
// ---------------------------------------------------------------------------

export function useUpdateUserPreferences() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (payload: UserPreferenceUpdateRequest) => updateMyPreferences(payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['userPreferences'] })
      // Today's WatchlistCard and FavoriteButton may need to re-derive target watchlist
      void queryClient.invalidateQueries({ queryKey: ['watchlists'] })
    },
  })
}

// ---------------------------------------------------------------------------
// Derived: effective default watchlist ID
//   1. preference.default_watchlist_id (user-chosen)
//   2. the watchlist list's own default flag
//   3. the first watchlist in the list
// ---------------------------------------------------------------------------

export function useEffectiveDefaultWatchlistId(): number | null {
  const { data: prefs } = useUserPreferences()
  const fallbackId = useDefaultWatchlistId()

  if (prefs?.default_watchlist_id != null) {
    return prefs.default_watchlist_id
  }
  return fallbackId
}
