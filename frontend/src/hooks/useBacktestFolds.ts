import { useQuery } from '@tanstack/react-query'
import { apiFetch } from '@/api/client'
import type { BacktestFoldsResponse } from '@/api/types'

export function useBacktestFolds(runId: number | null | undefined) {
  return useQuery({
    queryKey: ['backtest', 'folds', runId],
    enabled: runId !== null && runId !== undefined,
    queryFn: () =>
      apiFetch<BacktestFoldsResponse>(`/api/backtest/runs/${runId}/folds`),
    staleTime: 60_000,
  })
}
