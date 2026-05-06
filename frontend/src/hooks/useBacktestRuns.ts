import { useQuery } from '@tanstack/react-query'
import { apiFetch } from '@/api/client'
import type { BacktestRunsResponse } from '@/api/types'

export interface UseBacktestRunsParams {
  strategy?: string
  limit?: number
}

export function useBacktestRuns(params: UseBacktestRunsParams = {}) {
  const { strategy, limit = 20 } = params
  return useQuery({
    queryKey: ['backtest', 'runs', { strategy, limit }],
    queryFn: () =>
      apiFetch<BacktestRunsResponse>('/api/backtest/runs', {
        searchParams: { strategy, limit },
      }),
    staleTime: 60_000,
  })
}
