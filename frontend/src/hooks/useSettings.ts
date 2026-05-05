import { useQuery } from '@tanstack/react-query'
import { apiFetch } from '@/api/client'
import type { SettingsResponse } from '@/api/types'

export function useSettings() {
  return useQuery({
    queryKey: ['settings'],
    queryFn: () => apiFetch<SettingsResponse>('/api/settings'),
    staleTime: 5 * 60_000,
  })
}
