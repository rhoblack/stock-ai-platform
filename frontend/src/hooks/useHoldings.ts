import { useQuery } from '@tanstack/react-query'
import { apiFetch } from '@/api/client'
import type { HoldingsResponse } from '@/api/types'

export function useHoldings() {
  return useQuery({
    queryKey: ['holdings'],
    queryFn: () => apiFetch<HoldingsResponse>('/api/holdings'),
    refetchInterval: 60_000,
    staleTime: 30_000,
  })
}
