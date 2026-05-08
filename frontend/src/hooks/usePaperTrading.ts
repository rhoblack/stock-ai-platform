// v0.14 Phase E — Paper / Simulation Trading TanStack Query hooks.
//
// Read hooks have a 30s staleTime so the dashboard does not hammer the
// (in-process) backend. Mutation hooks invalidate the relevant queries
// after a successful POST / DELETE so the UI reflects the new state
// without a page reload.

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  cancelPaperOrder,
  fetchPaperAccount,
  fetchPaperOrders,
  fetchPaperPnl,
  fetchPaperPositions,
  submitPaperOrder,
} from '@/api/paper'
import type { CreatePaperOrderRequest } from '@/api/types'

const PAPER_KEY = ['paper'] as const

export function usePaperAccount(accountId?: number) {
  return useQuery({
    queryKey: [...PAPER_KEY, 'account', accountId ?? null],
    queryFn: () => fetchPaperAccount(accountId ? { account_id: accountId } : undefined),
    staleTime: 30_000,
    retry: false,
  })
}

export interface UsePaperOrdersParams {
  accountId?: number
  status?: string
  symbol?: string
  limit?: number
}

export function usePaperOrders(params: UsePaperOrdersParams = {}) {
  return useQuery({
    queryKey: [
      ...PAPER_KEY,
      'orders',
      params.accountId ?? null,
      params.status ?? null,
      params.symbol ?? null,
      params.limit ?? null,
    ],
    queryFn: () =>
      fetchPaperOrders({
        account_id: params.accountId,
        status: params.status,
        symbol: params.symbol,
        limit: params.limit,
      }),
    staleTime: 15_000,
    retry: false,
  })
}

export function usePaperPositions(accountId?: number, includeClosed = false) {
  return useQuery({
    queryKey: [...PAPER_KEY, 'positions', accountId ?? null, includeClosed],
    queryFn: () =>
      fetchPaperPositions({
        account_id: accountId,
        include_closed: includeClosed || undefined,
      }),
    staleTime: 30_000,
    retry: false,
  })
}

export interface UsePaperPnlParams {
  accountId?: number
  fromDate?: string
  toDate?: string
  limit?: number
}

export function usePaperPnl(params: UsePaperPnlParams = {}) {
  return useQuery({
    queryKey: [
      ...PAPER_KEY,
      'pnl',
      params.accountId ?? null,
      params.fromDate ?? null,
      params.toDate ?? null,
      params.limit ?? null,
    ],
    queryFn: () =>
      fetchPaperPnl({
        account_id: params.accountId,
        from_date: params.fromDate,
        to_date: params.toDate,
        limit: params.limit,
      }),
    staleTime: 60_000,
    retry: false,
  })
}

export function useSubmitPaperOrder() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (payload: CreatePaperOrderRequest) => submitPaperOrder(payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: PAPER_KEY })
    },
  })
}

export function useCancelPaperOrder() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ orderId, reason }: { orderId: number; reason?: string }) =>
      cancelPaperOrder(orderId, reason),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: PAPER_KEY })
    },
  })
}
