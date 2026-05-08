// v0.16 Phase E — Real Orders read-only API client.
//
// All calls are GET — there are NO mutation endpoints (no POST/PUT/DELETE).
// This module NEVER contacts KIS / a real broker / any external service.
// It calls /api/real-orders/* which returns DRY_RUN records only in Phase D/E.

import { apiFetch } from './client'
import type {
  RealOrderDetailResponse,
  RealOrdersResponse,
} from './types'

export function fetchRealOrders(params?: {
  status?: string
  candidate_id?: number
  limit?: number
  offset?: number
}): Promise<RealOrdersResponse> {
  return apiFetch<RealOrdersResponse>('/api/real-orders', {
    searchParams: params,
  })
}

export function fetchRealOrderDetail(orderId: number): Promise<RealOrderDetailResponse> {
  return apiFetch<RealOrderDetailResponse>(`/api/real-orders/${orderId}`)
}
