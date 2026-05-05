import { useQuery } from '@tanstack/react-query'
import { apiFetch } from '@/api/client'
import type { RecommendationHistoryResponse } from '@/api/types'

export interface UseRecommendationHistoryOptions {
  limit?: number
  offset?: number
  startDate?: string
  endDate?: string
}

export function useRecommendationHistory(options: UseRecommendationHistoryOptions = {}) {
  const { limit = 20, offset = 0, startDate, endDate } = options
  return useQuery({
    queryKey: ['recommendations', 'history', { limit, offset, startDate, endDate }],
    queryFn: () =>
      apiFetch<RecommendationHistoryResponse>('/api/recommendations/history', {
        searchParams: {
          limit,
          offset,
          start_date: startDate,
          end_date: endDate,
        },
      }),
    refetchInterval: 5 * 60_000,
    staleTime: 60_000,
  })
}
