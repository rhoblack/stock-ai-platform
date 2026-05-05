import { useQuery } from '@tanstack/react-query'
import { apiFetch } from '@/api/client'
import type { HoldingCheckSymbolResponse } from '@/api/types'

export function useHoldingChecksForSymbol(
  symbol: string | null | undefined,
  options: { limit?: number } = {},
) {
  const { limit = 20 } = options
  return useQuery({
    queryKey: ['holdings', 'checks', 'symbol', symbol, limit],
    enabled: !!symbol,
    queryFn: () =>
      apiFetch<HoldingCheckSymbolResponse>(`/api/holdings/${symbol}/checks`, {
        searchParams: { limit },
      }),
    refetchInterval: 60_000,
    staleTime: 30_000,
  })
}
