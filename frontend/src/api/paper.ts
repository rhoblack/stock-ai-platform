// v0.14 Phase E — Paper / Simulation Trading API client.
//
// All calls go to /api/paper/* — there is NO KIS / real-broker / autotrade
// endpoint anywhere in this module. mutation calls (submitPaperOrder,
// cancelPaperOrder) hit POST/DELETE under /api/paper/orders, which the
// backend returns 503 for when PAPER_TRADING_ENABLED=false.

import { apiDelete, apiFetch, apiPost } from './client'
import type {
  CreatePaperOrderRequest,
  PaperAccount,
  PaperOrderResponse,
  PaperOrdersResponse,
  PaperPnLResponse,
  PaperPositionsResponse,
  PaperStatusResponse,
} from './types'

export function fetchPaperAccount(params?: {
  account_id?: number
}): Promise<PaperAccount> {
  return apiFetch<PaperAccount>('/api/paper/account', {
    searchParams: params,
  })
}

export function fetchPaperOrders(params?: {
  account_id?: number
  status?: string
  symbol?: string
  limit?: number
}): Promise<PaperOrdersResponse> {
  return apiFetch<PaperOrdersResponse>('/api/paper/orders', {
    searchParams: params,
  })
}

export function fetchPaperPositions(params?: {
  account_id?: number
  include_closed?: boolean
}): Promise<PaperPositionsResponse> {
  return apiFetch<PaperPositionsResponse>('/api/paper/positions', {
    searchParams: params,
  })
}

export function fetchPaperPnl(params?: {
  account_id?: number
  from_date?: string
  to_date?: string
  limit?: number
}): Promise<PaperPnLResponse> {
  return apiFetch<PaperPnLResponse>('/api/paper/pnl', {
    searchParams: params,
  })
}

export function submitPaperOrder(
  payload: CreatePaperOrderRequest,
): Promise<PaperOrderResponse> {
  return apiPost<PaperOrderResponse, CreatePaperOrderRequest>(
    '/api/paper/orders',
    payload,
  )
}

export function cancelPaperOrder(
  orderId: number,
  reason?: string,
): Promise<PaperStatusResponse> {
  const qs = reason ? `?reason=${encodeURIComponent(reason)}` : ''
  return apiDelete<PaperStatusResponse>(`/api/paper/orders/${orderId}${qs}`)
}
