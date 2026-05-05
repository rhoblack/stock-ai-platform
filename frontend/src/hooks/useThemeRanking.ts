import { useQuery } from '@tanstack/react-query'
import { apiFetch } from '@/api/client'
import type { ThemeRankingResponse } from '@/api/types'

export interface UseThemeRankingOptions {
  category?: string
  direction?: string
  limit?: number
  enabled?: boolean
}

export function useThemeRanking(options: UseThemeRankingOptions = {}) {
  const { category, direction, limit = 50, enabled = true } = options
  return useQuery({
    queryKey: ['themes', 'ranking', { category, direction, limit }],
    enabled,
    queryFn: () =>
      apiFetch<ThemeRankingResponse>('/api/themes/ranking', {
        searchParams: { category, direction, limit },
      }),
    staleTime: 5 * 60_000,
  })
}
