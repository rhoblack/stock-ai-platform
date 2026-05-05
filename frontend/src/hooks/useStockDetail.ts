import { useQuery } from '@tanstack/react-query'
import { apiFetch } from '@/api/client'
import type { StockDetailResponse } from '@/api/types'

export interface UseStockDetailOptions {
  recommendationLimit?: number
  holdingCheckLimit?: number
}

export function useStockDetail(
  symbol: string | null | undefined,
  options: UseStockDetailOptions = {},
) {
  const { recommendationLimit = 10, holdingCheckLimit = 20 } = options
  return useQuery({
    queryKey: ['stocks', symbol, { recommendationLimit, holdingCheckLimit }],
    enabled: !!symbol,
    queryFn: () =>
      apiFetch<StockDetailResponse>(`/api/stocks/${symbol}`, {
        searchParams: {
          recommendation_limit: recommendationLimit,
          holding_check_limit: holdingCheckLimit,
        },
      }),
    staleTime: 60_000,
  })
}
