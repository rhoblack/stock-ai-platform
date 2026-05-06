import { useQuery } from '@tanstack/react-query'
import { apiFetch } from '@/api/client'
import type { StockEarningsResponse } from '@/api/types'

export function useStockEarnings(
  symbol: string | null | undefined,
  limit = 8,
) {
  return useQuery({
    queryKey: ['stocks', symbol, 'earnings', { limit }],
    enabled: !!symbol,
    queryFn: () =>
      apiFetch<StockEarningsResponse>(`/api/stocks/${symbol}/earnings`, {
        searchParams: { limit },
      }),
    staleTime: 60_000,
  })
}
