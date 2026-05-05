import { useQuery } from '@tanstack/react-query'
import { apiFetch } from '@/api/client'
import type { HoldingChecksResponse } from '@/api/types'

export function useLatestHoldingChecks(checkType?: 'PRE_MARKET' | 'POST_MARKET') {
  return useQuery({
    queryKey: ['holdings', 'checks', 'latest', checkType ?? 'ALL'],
    queryFn: () =>
      apiFetch<HoldingChecksResponse>('/api/holdings/checks/latest', {
        searchParams: { check_type: checkType },
      }),
    refetchInterval: 60_000,
    staleTime: 30_000,
  })
}
