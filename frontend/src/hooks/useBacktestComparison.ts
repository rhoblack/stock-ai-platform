import { useQuery } from '@tanstack/react-query'
import { apiFetch } from '@/api/client'
import type { BacktestComparisonResponse } from '@/api/types'

export function useBacktestComparison(runId: number | null | undefined) {
  return useQuery({
    queryKey: ['backtest', 'comparison', runId],
    enabled: runId !== null && runId !== undefined,
    queryFn: () =>
      apiFetch<BacktestComparisonResponse>(`/api/backtest/runs/${runId}/comparison`),
    staleTime: 60_000,
  })
}
