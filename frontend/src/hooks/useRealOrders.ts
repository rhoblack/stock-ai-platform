// v0.16 Phase E — Real Orders TanStack Query hooks.
//
// Read-only hooks only — no mutation hooks. The /real-orders screen is a
// display-only dashboard for dry-run execution records.

import { useQuery } from '@tanstack/react-query'
import { fetchRealOrderDetail, fetchRealOrders } from '@/api/realOrders'

export const REAL_ORDERS_KEY = ['real-orders'] as const

export interface UseRealOrdersParams {
  status?: string
  candidateId?: number
  limit?: number
  offset?: number
}

export function useRealOrders(params: UseRealOrdersParams = {}) {
  return useQuery({
    queryKey: [
      ...REAL_ORDERS_KEY,
      'list',
      params.status ?? null,
      params.candidateId ?? null,
      params.limit ?? null,
      params.offset ?? null,
    ],
    queryFn: () =>
      fetchRealOrders({
        status: params.status,
        candidate_id: params.candidateId,
        limit: params.limit,
        offset: params.offset,
      }),
    staleTime: 15_000,
    retry: false,
  })
}

export function useRealOrderDetail(orderId: number | null) {
  return useQuery({
    queryKey: [...REAL_ORDERS_KEY, 'detail', orderId],
    queryFn: () => fetchRealOrderDetail(orderId as number),
    enabled: orderId !== null,
    staleTime: 30_000,
    retry: false,
  })
}
