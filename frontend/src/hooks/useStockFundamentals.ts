import { useQuery } from '@tanstack/react-query'
import { apiFetch } from '@/api/client'
import type { StockFundamentalsResponse } from '@/api/types'

export function useStockFundamentals(
  symbol: string | null | undefined,
  limit = 8,
) {
  return useQuery({
    queryKey: ['stocks', symbol, 'fundamentals', { limit }],
    enabled: !!symbol,
    queryFn: () =>
      apiFetch<StockFundamentalsResponse>(
        `/api/stocks/${symbol}/fundamentals`,
        { searchParams: { limit } },
      ),
    staleTime: 60_000,
  })
}
