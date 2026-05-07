// v0.10 Phase D — Provider Health React Query hook.
//
// Reads GET /api/health/providers and caches for 30 s so the Settings
// panel doesn't hammer the endpoint while the page sits open.

import { useQuery } from '@tanstack/react-query'
import { getProviderHealth } from '@/api/providerHealth'

export function useProviderHealth() {
  return useQuery({
    queryKey: ['providerHealth'],
    queryFn: getProviderHealth,
    staleTime: 30_000,
    // The endpoint is read-only and inexpensive; refresh once a minute
    // when the user is actively viewing Settings.
    refetchInterval: 60_000,
    // Avoid a thundering herd on tab focus when DART/RSS are disabled.
    refetchOnWindowFocus: false,
  })
}
