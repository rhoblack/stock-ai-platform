import { useQuery } from '@tanstack/react-query'
import { apiFetch } from '@/api/client'
import type { RecommendationRunDetailResponse } from '@/api/types'

export function useRecommendationRunDetail(runId: number | null | undefined) {
  return useQuery({
    queryKey: ['recommendations', 'run', runId],
    enabled: runId !== null && runId !== undefined && Number.isFinite(runId),
    queryFn: () =>
      apiFetch<RecommendationRunDetailResponse>(`/api/recommendations/${runId}`),
    staleTime: 60_000,
  })
}
