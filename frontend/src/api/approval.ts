// v0.15 Phase E — Approval Workflow API client.
//
// All calls go to /api/approvals/* — there is NO KIS / real-broker /
// autotrade endpoint anywhere in this module. mutation calls (submit /
// approve / reject / expire) hit POST under /api/approvals/..., which the
// backend returns 503 for when TRADING_SAFETY_ENABLED=false or
// KILL_SWITCH_ENABLED=true. Approved candidates are forwarded by the
// backend to SimulationBroker.submit_order — this client never touches a
// real broker.

import { apiFetch, apiPost } from './client'
import type {
  ApprovalAuditResponse,
  ApprovalCandidateStatusResponse,
  ApproveCandidateResponse,
  CreateOrderCandidateRequest,
  CreateOrderCandidateResponse,
  OrderCandidateDetailResponse,
  OrderCandidatesResponse,
} from './types'

export function fetchApprovalCandidates(params?: {
  status?: string
  account_id?: number
  limit?: number
}): Promise<OrderCandidatesResponse> {
  return apiFetch<OrderCandidatesResponse>('/api/approvals/candidates', {
    searchParams: params,
  })
}

export function fetchApprovalCandidate(
  candidateId: number,
): Promise<OrderCandidateDetailResponse> {
  return apiFetch<OrderCandidateDetailResponse>(
    `/api/approvals/candidates/${candidateId}`,
  )
}

export function fetchApprovalAudit(params?: {
  candidate_id?: number
  event_type?: string
  limit?: number
}): Promise<ApprovalAuditResponse> {
  return apiFetch<ApprovalAuditResponse>('/api/approvals/audit', {
    searchParams: params,
  })
}

export function submitApprovalCandidate(
  payload: CreateOrderCandidateRequest,
): Promise<CreateOrderCandidateResponse> {
  return apiPost<CreateOrderCandidateResponse, CreateOrderCandidateRequest>(
    '/api/approvals/candidates',
    payload,
  )
}

export function approveCandidate(
  candidateId: number,
): Promise<ApproveCandidateResponse> {
  return apiPost<ApproveCandidateResponse, Record<string, never>>(
    `/api/approvals/${candidateId}/approve`,
    {},
  )
}

export function rejectCandidate(
  candidateId: number,
  reason: string,
): Promise<ApprovalCandidateStatusResponse> {
  return apiPost<ApprovalCandidateStatusResponse, { reason: string }>(
    `/api/approvals/${candidateId}/reject`,
    { reason },
  )
}

export function expireCandidate(
  candidateId: number,
): Promise<ApprovalCandidateStatusResponse> {
  return apiPost<ApprovalCandidateStatusResponse, Record<string, never>>(
    `/api/approvals/${candidateId}/expire`,
    {},
  )
}
