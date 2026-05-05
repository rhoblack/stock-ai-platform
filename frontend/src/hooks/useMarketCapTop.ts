import { useQuery } from '@tanstack/react-query'
import { apiFetch } from '@/api/client'
import type { MarketCapRankingResponse } from '@/api/types'

export interface UseMarketCapTopOptions {
  market?: string
  rankDate?: string
  limit?: number
  enabled?: boolean
}

export function useMarketCapTop(options: UseMarketCapTopOptions = {}) {
  const { market = 'KOSPI', rankDate, limit = 50, enabled = true } = options
  return useQuery({
    queryKey: ['universe', 'market-cap-top', { market, rankDate, limit }],
    enabled,
    queryFn: () =>
      apiFetch<MarketCapRankingResponse>('/api/universe/market-cap-top', {
        searchParams: { market, rank_date: rankDate, limit },
      }),
    refetchInterval: 60 * 60_000,
    staleTime: 30 * 60_000,
  })
}
