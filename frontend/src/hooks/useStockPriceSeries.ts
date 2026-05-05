import { useQuery } from '@tanstack/react-query'
import { apiFetch } from '@/api/client'
import type { StockPriceSeriesResponse } from '@/api/types'

export interface UseStockPriceSeriesOptions {
  /** 1 ~ 500. 기본 120. 백엔드도 같은 범위 검증. */
  days?: number
}

export function useStockPriceSeries(
  symbol: string | null | undefined,
  options: UseStockPriceSeriesOptions = {},
) {
  const { days = 120 } = options
  return useQuery({
    queryKey: ['stocks', symbol, 'prices', { days }],
    enabled: !!symbol,
    queryFn: () =>
      apiFetch<StockPriceSeriesResponse>(`/api/stocks/${symbol}/prices`, {
        searchParams: { days },
      }),
    staleTime: 60_000,
  })
}
