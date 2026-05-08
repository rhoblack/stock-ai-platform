// v0.15 Phase E — Approval Workflow TanStack Query hooks.
//
// Mutation hooks invalidate both the approval namespace and the paper
// namespace after success: an approval that lands at EXECUTED_PAPER
// produces a new VirtualOrder which the /paper screen also wants to
// reflect.

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  approveCandidate,
  expireCandidate,
  fetchApprovalAudit,
  fetchApprovalCandidate,
  fetchApprovalCandidates,
  rejectCandidate,
  submitApprovalCandidate,
} from '@/api/approval'
import type { CreateOrderCandidateRequest } from '@/api/types'

const APPROVAL_KEY = ['approval'] as const
const PAPER_KEY = ['paper'] as const

export interface UseApprovalCandidatesParams {
  status?: string
  accountId?: number
  limit?: number
}

export function useApprovalCandidates(
  params: UseApprovalCandidatesParams = {},
) {
  return useQuery({
    queryKey: [
      ...APPROVAL_KEY,
      'candidates',
      params.status ?? null,
      params.accountId ?? null,
      params.limit ?? null,
    ],
    queryFn: () =>
      fetchApprovalCandidates({
        status: params.status,
        account_id: params.accountId,
        limit: params.limit,
      }),
    staleTime: 15_000,
    retry: false,
  })
}

export function useApprovalCandidate(candidateId: number | null) {
  return useQuery({
    queryKey: [...APPROVAL_KEY, 'candidate', candidateId],
    queryFn: () => fetchApprovalCandidate(candidateId as number),
    enabled: candidateId !== null,
    staleTime: 30_000,
    retry: false,
  })
}

export interface UseApprovalAuditParams {
  candidateId?: number
  eventType?: string
  limit?: number
}

export function useApprovalAudit(params: UseApprovalAuditParams = {}) {
  return useQuery({
    queryKey: [
      ...APPROVAL_KEY,
      'audit',
      params.candidateId ?? null,
      params.eventType ?? null,
      params.limit ?? null,
    ],
    queryFn: () =>
      fetchApprovalAudit({
        candidate_id: params.candidateId,
        event_type: params.eventType,
        limit: params.limit,
      }),
    staleTime: 30_000,
    retry: false,
  })
}

function _invalidateAll(qc: ReturnType<typeof useQueryClient>): void {
  qc.invalidateQueries({ queryKey: APPROVAL_KEY })
  // EXECUTED_PAPER lands a VirtualOrder -- the paper screen wants to refresh.
  qc.invalidateQueries({ queryKey: PAPER_KEY })
}

export function useSubmitApprovalCandidate() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (payload: CreateOrderCandidateRequest) =>
      submitApprovalCandidate(payload),
    onSuccess: () => _invalidateAll(qc),
  })
}

export function useApproveCandidate() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (candidateId: number) => approveCandidate(candidateId),
    onSuccess: () => _invalidateAll(qc),
  })
}

export function useRejectCandidate() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({
      candidateId,
      reason,
    }: {
      candidateId: number
      reason: string
    }) => rejectCandidate(candidateId, reason),
    onSuccess: () => _invalidateAll(qc),
  })
}

export function useExpireCandidate() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (candidateId: number) => expireCandidate(candidateId),
    onSuccess: () => _invalidateAll(qc),
  })
}
