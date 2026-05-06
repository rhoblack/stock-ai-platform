import { useQuery } from '@tanstack/react-query'
import { apiFetch } from '@/api/client'
import type { BacktestRunDetailResponse } from '@/api/types'

export function useBacktestRunDetail(runId: number | null | undefined) {
  return useQuery({
    queryKey: ['backtest', 'runs', runId],
    enabled: runId !== null && runId !== undefined,
    queryFn: () =>
      apiFetch<BacktestRunDetailResponse>(`/api/backtest/runs/${runId}`),
    staleTime: 60_000,
  })
}
