import { useQuery } from '@tanstack/react-query'
import { apiFetch } from '@/api/client'
import type { StrategiesResponse } from '@/api/types'

// Strategy registry rarely changes (tied to backend release) — 5분 캐시.
export function useStrategies() {
  return useQuery({
    queryKey: ['backtest', 'strategies'],
    queryFn: () => apiFetch<StrategiesResponse>('/api/strategies'),
    staleTime: 5 * 60_000,
  })
}
