// v0.15 Phase E — Approvals page vitest suite.
//
// Mirrors the PaperTrading suite: GET fixtures + msw POST overrides via
// `server.use(...)` so the page can exercise the disabled (503) and
// happy-path branches without hitting any real broker.

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, screen, waitFor } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { renderWithProviders } from './renderWithProviders'
import { server } from './mswServer'
import { ApprovalsPage } from '@/pages/Approvals'

const PENDING_CANDIDATES = {
  candidates: [
    {
      id: 11,
      account_id: 1,
      source: 'MANUAL',
      source_ref_id: null,
      symbol: '005930',
      side: 'BUY',
      quantity: 10,
      order_type: 'MARKET',
      limit_price: null,
      estimated_amount: '700000',
      status: 'PENDING_APPROVAL' as const,
      rejection_reason: null,
      expires_at: '2026-05-08T17:00:00',
      virtual_order_id: null,
      approver_user_id: null,
      created_at: '2026-05-08T16:00:00',
      updated_at: '2026-05-08T16:00:00',
    },
  ],
  total: 1,
  limit: 50,
}

const REJECTED_CANDIDATES = {
  candidates: [
    {
      id: 9,
      account_id: 1,
      source: 'MANUAL',
      source_ref_id: null,
      symbol: '000660',
      side: 'BUY',
      quantity: 5,
      order_type: 'LIMIT',
      limit_price: '180000',
      estimated_amount: '900000',
      status: 'REJECTED' as const,
      rejection_reason: '운영자 거절',
      expires_at: null,
      virtual_order_id: null,
      approver_user_id: 1,
      created_at: '2026-05-08T15:00:00',
      updated_at: '2026-05-08T15:30:00',
    },
  ],
  total: 1,
  limit: 20,
}

const CANDIDATE_DETAIL_11 = {
  candidate: PENDING_CANDIDATES.candidates[0],
  risk_check_result: {
    policy_version: 'v1',
    passed: true,
    violations: [],
    checked_at: '2026-05-08T16:00:01',
  },
}

const CANDIDATE_DETAIL_RISK_FAIL = {
  candidate: { ...PENDING_CANDIDATES.candidates[0], status: 'RISK_REJECTED' as const },
  risk_check_result: {
    policy_version: 'v1',
    passed: false,
    violations: [
      {
        rule_id: 'per_symbol_limit',
        severity: 'HARD',
        message: '종목당 한도 초과',
        details: { limit: 5 },
      },
    ],
    checked_at: '2026-05-08T16:00:01',
  },
}

const AUDIT_RESPONSE = {
  items: [
    {
      id: 1,
      candidate_id: 11,
      event_type: 'CREATED' as const,
      user_id: 1,
      reason: null,
      details: null,
      created_at: '2026-05-08T16:00:00',
    },
    {
      id: 2,
      candidate_id: 11,
      event_type: 'RISK_CHECKED' as const,
      user_id: 1,
      reason: null,
      details: null,
      created_at: '2026-05-08T16:00:01',
    },
  ],
  total: 2,
  limit: 50,
}

const FORBIDDEN_SUBSTRINGS = [
  'api_key',
  'access_token',
  'jwt_secret',
  'kis_app_secret',
  'kis_account_no',
  'source_file_path',
  'broker_order_id',
  'kis_order_id',
  'real_account',
  'real_order_id',
  'account_number',
  'raw_text',
  'full_text',
]

// These phrases must not appear anywhere on the page (banners, copy,
// labels). The intentionally-allowed safety copy "실 KIS 주문 / 자동매매
// / 실거래 호출 0건" is part of the policy banner and is fine because the
// FORBIDDEN list below is the *actionable* automation vocabulary.
const FORBIDDEN_AUTOMATION_PHRASES = [
  '자동매매 시작',
  '자동매매 모드',
  '실거래 시작',
  '실거래 모드',
  'FULL_AUTO',
  'SMALL_AUTO',
  'place real order',
]

describe('ApprovalsPage', () => {
  let promptSpy: ReturnType<typeof vi.fn>

  beforeEach(() => {
    promptSpy = vi.fn(() => '운영자 거절')
    vi.stubGlobal('prompt', promptSpy)
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('renders approvals-page wrapper, policy banner and new candidate form', () => {
    renderWithProviders(<ApprovalsPage />, { initialEntries: ['/approvals'] })
    expect(screen.getByTestId('approvals-page')).toBeInTheDocument()
    expect(screen.getByTestId('approvals-policy-banner')).toBeInTheDocument()
    expect(screen.getByTestId('approvals-new-form')).toBeInTheDocument()
    expect(screen.getByTestId('approvals-new-submit')).toHaveTextContent(
      '후보 만들기 (Risk Check)',
    )
  })

  it('shows the empty-state placeholder when no pending candidates exist', async () => {
    renderWithProviders(<ApprovalsPage />, { initialEntries: ['/approvals'] })
    await waitFor(() =>
      expect(screen.getByTestId('approvals-pending-empty')).toBeInTheDocument(),
    )
    expect(screen.getByTestId('approvals-history-empty')).toBeInTheDocument()
  })

  it('renders pending candidates table with action buttons when candidates exist', async () => {
    server.use(
      http.get('*/api/approvals/candidates', () =>
        HttpResponse.json(PENDING_CANDIDATES),
      ),
    )
    renderWithProviders(<ApprovalsPage />, { initialEntries: ['/approvals'] })
    await waitFor(() =>
      expect(screen.getByTestId('approvals-pending-table')).toBeInTheDocument(),
    )
    expect(screen.getByTestId('approvals-row-11')).toBeInTheDocument()
    expect(screen.getByTestId('approvals-approve-11')).toHaveTextContent(
      '승인 (paper 실행)',
    )
    expect(screen.getByTestId('approvals-reject-11')).toHaveTextContent('거절')
    expect(screen.getByTestId('approvals-expire-11')).toHaveTextContent('만료')
  })

  it('shows the disabled banner when approve POST returns 503', async () => {
    server.use(
      http.get('*/api/approvals/candidates', () =>
        HttpResponse.json(PENDING_CANDIDATES),
      ),
      http.post('*/api/approvals/:id/approve', () =>
        HttpResponse.json(
          { detail: 'trading safety is disabled' },
          { status: 503 },
        ),
      ),
    )
    renderWithProviders(<ApprovalsPage />, { initialEntries: ['/approvals'] })
    await waitFor(() =>
      expect(screen.getByTestId('approvals-approve-11')).toBeInTheDocument(),
    )
    fireEvent.click(screen.getByTestId('approvals-approve-11'))
    await waitFor(() =>
      expect(screen.getByTestId('approvals-disabled-banner')).toBeInTheDocument(),
    )
    expect(screen.queryByTestId('approvals-approve-success')).not.toBeInTheDocument()
  })

  it('shows the kill switch banner when 503 detail mentions kill switch', async () => {
    server.use(
      http.get('*/api/approvals/candidates', () =>
        HttpResponse.json(PENDING_CANDIDATES),
      ),
      http.post('*/api/approvals/:id/approve', () =>
        HttpResponse.json(
          { detail: 'kill switch is ON — all approvals blocked' },
          { status: 503 },
        ),
      ),
    )
    renderWithProviders(<ApprovalsPage />, { initialEntries: ['/approvals'] })
    await waitFor(() =>
      expect(screen.getByTestId('approvals-approve-11')).toBeInTheDocument(),
    )
    fireEvent.click(screen.getByTestId('approvals-approve-11'))
    await waitFor(() =>
      expect(screen.getByTestId('approvals-kill-switch-banner')).toBeInTheDocument(),
    )
  })

  it('approves a candidate and shows the success banner with virtual_order_id', async () => {
    server.use(
      http.get('*/api/approvals/candidates', () =>
        HttpResponse.json(PENDING_CANDIDATES),
      ),
      http.post('*/api/approvals/:id/approve', async ({ params }) => {
        expect(params.id).toBe('11')
        return HttpResponse.json({
          candidate: {
            ...PENDING_CANDIDATES.candidates[0],
            status: 'EXECUTED_PAPER' as const,
            virtual_order_id: 999,
          },
          virtual_order_id: 999,
        })
      }),
    )
    renderWithProviders(<ApprovalsPage />, { initialEntries: ['/approvals'] })
    await waitFor(() =>
      expect(screen.getByTestId('approvals-approve-11')).toBeInTheDocument(),
    )
    fireEvent.click(screen.getByTestId('approvals-approve-11'))
    await waitFor(() =>
      expect(screen.getByTestId('approvals-approve-success')).toBeInTheDocument(),
    )
    expect(screen.getByTestId('approvals-approve-success')).toHaveTextContent('999')
  })

  it('rejects a candidate via prompt-driven reason', async () => {
    server.use(
      http.get('*/api/approvals/candidates', () =>
        HttpResponse.json(PENDING_CANDIDATES),
      ),
      http.post('*/api/approvals/:id/reject', async ({ request, params }) => {
        const body = (await request.json()) as Record<string, unknown>
        expect(params.id).toBe('11')
        expect(body.reason).toBe('운영자 거절')
        return HttpResponse.json({
          status: 'ok',
          candidate_id: 11,
          new_status: 'REJECTED' as const,
        })
      }),
    )
    renderWithProviders(<ApprovalsPage />, { initialEntries: ['/approvals'] })
    await waitFor(() =>
      expect(screen.getByTestId('approvals-reject-11')).toBeInTheDocument(),
    )
    fireEvent.click(screen.getByTestId('approvals-reject-11'))
    await waitFor(() => expect(promptSpy).toHaveBeenCalled())
  })

  it('expires a candidate via the expire button', async () => {
    let expireCalls = 0
    server.use(
      http.get('*/api/approvals/candidates', () =>
        HttpResponse.json(PENDING_CANDIDATES),
      ),
      http.post('*/api/approvals/:id/expire', () => {
        expireCalls += 1
        return HttpResponse.json({
          status: 'ok',
          candidate_id: 11,
          new_status: 'EXPIRED' as const,
        })
      }),
    )
    renderWithProviders(<ApprovalsPage />, { initialEntries: ['/approvals'] })
    await waitFor(() =>
      expect(screen.getByTestId('approvals-expire-11')).toBeInTheDocument(),
    )
    fireEvent.click(screen.getByTestId('approvals-expire-11'))
    await waitFor(() => expect(expireCalls).toBeGreaterThan(0))
  })

  it('opens the detail drawer with candidate summary, risk panel and audit timeline', async () => {
    server.use(
      http.get('*/api/approvals/candidates', () =>
        HttpResponse.json(PENDING_CANDIDATES),
      ),
      http.get('*/api/approvals/candidates/11', () =>
        HttpResponse.json(CANDIDATE_DETAIL_11),
      ),
      http.get('*/api/approvals/audit', () => HttpResponse.json(AUDIT_RESPONSE)),
    )
    renderWithProviders(<ApprovalsPage />, { initialEntries: ['/approvals'] })
    await waitFor(() =>
      expect(screen.getByTestId('approvals-row-11')).toBeInTheDocument(),
    )
    fireEvent.click(screen.getByTestId('approvals-row-11'))
    await waitFor(() =>
      expect(screen.getByTestId('approvals-detail-summary')).toBeInTheDocument(),
    )
    expect(screen.getByTestId('approvals-detail-drawer')).toBeInTheDocument()
    expect(screen.getByTestId('approvals-detail-risk')).toBeInTheDocument()
    expect(screen.getByTestId('approvals-detail-audit')).toBeInTheDocument()
    await waitFor(() =>
      expect(screen.getByTestId('approvals-audit-row-1')).toBeInTheDocument(),
    )
    expect(screen.getByTestId('approvals-audit-row-2')).toBeInTheDocument()
  })

  it('renders risk violation rows when the candidate has HARD violations', async () => {
    server.use(
      http.get('*/api/approvals/candidates', () =>
        HttpResponse.json(PENDING_CANDIDATES),
      ),
      http.get('*/api/approvals/candidates/11', () =>
        HttpResponse.json(CANDIDATE_DETAIL_RISK_FAIL),
      ),
    )
    renderWithProviders(<ApprovalsPage />, { initialEntries: ['/approvals'] })
    await waitFor(() =>
      expect(screen.getByTestId('approvals-row-11')).toBeInTheDocument(),
    )
    fireEvent.click(screen.getByTestId('approvals-row-11'))
    await waitFor(() =>
      expect(
        screen.getByTestId('approvals-detail-violation-per_symbol_limit'),
      ).toBeInTheDocument(),
    )
  })

  it('shows history table when terminal candidates exist', async () => {
    server.use(
      http.get('*/api/approvals/candidates', ({ request }) => {
        const url = new URL(request.url)
        const status = url.searchParams.get('status')
        if (status === 'REJECTED') {
          return HttpResponse.json(REJECTED_CANDIDATES)
        }
        return HttpResponse.json({ candidates: [], total: 0, limit: 50 })
      }),
    )
    renderWithProviders(<ApprovalsPage />, { initialEntries: ['/approvals'] })
    await waitFor(() =>
      expect(screen.getByTestId('approvals-history-table')).toBeInTheDocument(),
    )
    expect(screen.getByTestId('approvals-history-row-9')).toBeInTheDocument()
  })

  it('shows the disabled banner when submitting a new candidate gets 503', async () => {
    renderWithProviders(<ApprovalsPage />, { initialEntries: ['/approvals'] })
    fireEvent.change(screen.getByTestId('approvals-new-symbol-input'), {
      target: { value: '005930' },
    })
    fireEvent.change(screen.getByTestId('approvals-new-quantity-input'), {
      target: { value: '10' },
    })
    fireEvent.click(screen.getByTestId('approvals-new-submit'))
    await waitFor(() =>
      expect(screen.getByTestId('approvals-new-disabled-banner')).toBeInTheDocument(),
    )
  })

  it('submits a new candidate and shows the success banner', async () => {
    server.use(
      http.post('*/api/approvals/candidates', async ({ request }) => {
        const body = (await request.json()) as Record<string, unknown>
        expect(body.symbol).toBe('005930')
        expect(body.side).toBe('BUY')
        expect(body.quantity).toBe(10)
        return HttpResponse.json({
          candidate: {
            ...PENDING_CANDIDATES.candidates[0],
            id: 21,
            status: 'PENDING_APPROVAL' as const,
          },
          risk_check_result: {
            policy_version: 'v1',
            passed: true,
            violations: [],
            checked_at: '2026-05-08T16:30:00',
          },
          risk_passed: true,
        })
      }),
    )
    renderWithProviders(<ApprovalsPage />, { initialEntries: ['/approvals'] })
    fireEvent.change(screen.getByTestId('approvals-new-symbol-input'), {
      target: { value: '005930' },
    })
    fireEvent.change(screen.getByTestId('approvals-new-quantity-input'), {
      target: { value: '10' },
    })
    fireEvent.click(screen.getByTestId('approvals-new-submit'))
    await waitFor(() =>
      expect(screen.getByTestId('approvals-new-success')).toBeInTheDocument(),
    )
    expect(screen.getByTestId('approvals-new-success')).toHaveTextContent('21')
  })

  it('does NOT render forbidden response field labels', async () => {
    server.use(
      http.get('*/api/approvals/candidates', () =>
        HttpResponse.json(PENDING_CANDIDATES),
      ),
      http.get('*/api/approvals/candidates/11', () =>
        HttpResponse.json(CANDIDATE_DETAIL_11),
      ),
      http.get('*/api/approvals/audit', () => HttpResponse.json(AUDIT_RESPONSE)),
    )
    const { container } = renderWithProviders(<ApprovalsPage />, {
      initialEntries: ['/approvals'],
    })
    await waitFor(() =>
      expect(screen.getByTestId('approvals-pending-table')).toBeInTheDocument(),
    )
    fireEvent.click(screen.getByTestId('approvals-row-11'))
    await waitFor(() =>
      expect(screen.getByTestId('approvals-detail-drawer')).toBeInTheDocument(),
    )
    const text = (container.textContent ?? '').toLowerCase()
    for (const needle of FORBIDDEN_SUBSTRINGS) {
      expect(text).not.toContain(needle.toLowerCase())
    }
  })

  it('does NOT render any automation / autotrade CTA copy', () => {
    renderWithProviders(<ApprovalsPage />, { initialEntries: ['/approvals'] })
    const root = screen.getByTestId('approvals-page')
    const text = root.textContent ?? ''
    for (const phrase of FORBIDDEN_AUTOMATION_PHRASES) {
      expect(text).not.toContain(phrase)
    }
    expect(screen.getByTestId('approvals-new-submit')).toHaveTextContent(
      '후보 만들기 (Risk Check)',
    )
  })
})
