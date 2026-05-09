// v0.16 Phase E — Real Orders read-only API client.
// v1.0 Phase D — adds the SOLE mutation: POST /api/real-orders/{id}/sync.
//
// Read-only paths (GET only): /api/real-orders, /api/real-orders/{id}.
// Mutation: /api/real-orders/{id}/sync — manual fill-status sync only.
// This module NEVER contacts KIS / a real broker / any external service —
// the backend forwards through HttpxKisOrderTransport (Phase B) when an
// operator explicitly wires it. Tests use MSW + httpx.MockTransport mocks.

import { apiFetch, apiPost } from './client'
import type {
  RealOrderDetailResponse,
  RealOrderSyncRequest,
  RealOrderSyncResponse,
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

// v1.0 Phase D — manual Sync Fill trigger.
//
// The optional ``kis_order_no`` body field is the plaintext KIS order
// number when the operator holds it out-of-band (e.g. from KIS HTS).
// The backend NEVER persists or echoes it — this client passes it
// through to the FillSyncService transport in-memory only. The response
// excludes broker_order_no, account_number, raw_response, secrets, etc.
export function syncRealOrder(
  orderId: number,
  body?: RealOrderSyncRequest,
): Promise<RealOrderSyncResponse> {
  return apiPost<RealOrderSyncResponse, RealOrderSyncRequest>(
    `/api/real-orders/${orderId}/sync`,
    body ?? {},
  )
}
