// v0.16 Phase E — Real Orders TanStack Query hooks (read-only).
// v1.0 Phase D — adds the SOLE mutation hook: useSyncRealOrder.
//
// Read-only hooks (useRealOrders / useRealOrderDetail) are unchanged.
// useSyncRealOrder posts to /api/real-orders/{id}/sync — manual fill sync only.
// On success it invalidates the entire real-orders namespace so the table
// + detail panel refetch with the new fill rows / order status. Mutation
// retry is disabled (operator triggers manually; transient failures need
// human attention per RUNBOOK §6, not silent retries).

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  fetchRealOrderDetail,
  fetchRealOrders,
  syncRealOrder,
} from '@/api/realOrders'
import type { RealOrderSyncRequest } from '@/api/types'

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

// v1.0 Phase D — manual Sync Fill mutation hook.
//
// Invalidates the entire ``real-orders`` query namespace on success so the
// list + detail panel pick up the new RealFill row(s) and any
// RealOrder.status transition. ``retry: false`` — operator-triggered, no
// silent retry on transient failure (RUNBOOK §6 dictates manual followup).
export function useSyncRealOrder() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({
      orderId,
      body,
    }: {
      orderId: number
      body?: RealOrderSyncRequest
    }) => syncRealOrder(orderId, body),
    retry: false,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: REAL_ORDERS_KEY })
    },
  })
}
