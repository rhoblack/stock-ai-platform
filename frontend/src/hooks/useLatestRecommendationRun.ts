import { useQuery } from '@tanstack/react-query'
import { apiFetch } from '@/api/client'
import type { RecommendationRunDetailResponse } from '@/api/types'

export function useLatestRecommendationRun() {
  return useQuery({
    queryKey: ['recommendations', 'latest'],
    queryFn: () =>
      apiFetch<RecommendationRunDetailResponse>('/api/recommendations/latest'),
    refetchInterval: 5 * 60_000,
    staleTime: 60_000,
  })
}
