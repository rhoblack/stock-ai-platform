// v0.15 Phase E — Approval Workflow dashboard (/approvals).
//
// Hard policies enforced by this page:
//   - Calls go ONLY to /api/approvals/* — never to KIS / real broker.
//   - 503 on POST endpoints surfaces a friendly disabled banner; the
//     submit/approve/reject/expire buttons are kept visible but the
//     subsequent error banner explains the gate (TRADING_SAFETY_ENABLED
//     and/or KILL_SWITCH_ENABLED).
//   - Forbidden response fields (api_key / token / secret /
//     source_file_path / broker_order_id / kis_order_id / real_account /
//     real_order_id / account_number / raw_text / body / full_text) are
//     NEVER referenced — the schemas don't carry them and the page only
//     reads documented OrderCandidate / RiskCheckResult / Audit fields.
//   - All copy uses 승인 / 거절 / 만료 / paper / 시뮬레이션 vocabulary.
//     There is no "주문 실행" / "place real order" / "FULL_AUTO" /
//     "SMALL_AUTO" CTA anywhere on this page.

import { useMemo, useState, type FormEvent } from 'react'
import { Activity, ShieldAlert, ShieldCheck } from 'lucide-react'
import { ApiError } from '@/api/client'
import { cn } from '@/lib/utils'
import {
  useApprovalAudit,
  useApprovalCandidate,
  useApprovalCandidates,
  useApproveCandidate,
  useExpireCandidate,
  useRejectCandidate,
  useSubmitApprovalCandidate,
} from '@/hooks/useApprovals'
import type {
  ApprovalAuditLogItem,
  OrderCandidate,
  OrderCandidateStatus,
  RiskCheckResult,
} from '@/api/types'

const TERMINAL_STATUSES: ReadonlySet<OrderCandidateStatus> = new Set([
  'EXECUTED_PAPER',
  'REJECTED',
  'EXPIRED',
  'RISK_REJECTED',
])

function isDisabledError(err: unknown): boolean {
  return err instanceof ApiError && err.status === 503
}

function isKillSwitchError(err: unknown): boolean {
  if (!(err instanceof ApiError) || err.status !== 503) return false
  const detail = (err.message || '').toLowerCase()
  return detail.includes('kill switch')
}

function fmtDate(value: string | null | undefined): string {
  if (!value) return '—'
  try {
    return value.replace('T', ' ').slice(0, 19)
  } catch {
    return value
  }
}

function fmtNum(value: string | null | undefined): string {
  if (value === null || value === undefined || value === '') return '—'
  const num = Number(value)
  if (!Number.isFinite(num)) return value
  return num.toLocaleString('ko-KR', {
    maximumFractionDigits: 4,
    minimumFractionDigits: 0,
  })
}

export function ApprovalsPage() {
  const candidates = useApprovalCandidates({ status: undefined, limit: 50 })
  const history = useApprovalCandidates({ status: 'REJECTED', limit: 20 })
  const executed = useApprovalCandidates({ status: 'EXECUTED_PAPER', limit: 20 })
  const expired = useApprovalCandidates({ status: 'EXPIRED', limit: 20 })
  const riskRejected = useApprovalCandidates({ status: 'RISK_REJECTED', limit: 20 })

  const [selectedId, setSelectedId] = useState<number | null>(null)

  const recentHistory = useMemo<OrderCandidate[]>(() => {
    const seen = new Map<number, OrderCandidate>()
    for (const q of [history, executed, expired, riskRejected]) {
      if (!q.data) continue
      for (const c of q.data.candidates) {
        if (!seen.has(c.id)) seen.set(c.id, c)
      }
    }
    const all = Array.from(seen.values())
    all.sort((a, b) => b.id - a.id)
    return all.slice(0, 30)
  }, [history.data, executed.data, expired.data, riskRejected.data])

  return (
    <section className="flex flex-col gap-4" data-testid="approvals-page">
      <header className="flex flex-wrap items-end justify-between gap-2">
        <div>
          <h2 className="text-2xl font-semibold">승인 대기 (β)</h2>
          <p className="text-sm text-muted-foreground">
            Approval Trading Safety Layer — 승인된 후보는 SimulationBroker
            (paper execution) 만 호출합니다. 실 KIS 주문 / 자동매매 / 실거래 호출 0건.
          </p>
        </div>
        <div className="rounded-md border border-amber-200 bg-amber-50 px-3 py-1.5 text-xs text-amber-800 dark:border-amber-900/40 dark:bg-amber-900/20 dark:text-amber-200">
          <strong>모의투자</strong> 모드 — 승인은 paper execution 으로만 이어집니다
        </div>
      </header>

      <PolicyBanner />

      <PendingCandidatesTable
        loading={candidates.isLoading}
        error={candidates.isError}
        items={candidates.data?.candidates ?? []}
        onSelect={setSelectedId}
        selectedId={selectedId}
      />

      <CandidateDetailDrawer
        candidateId={selectedId}
        onClose={() => setSelectedId(null)}
      />

      <NewCandidateForm />

      <HistoryTable
        loading={
          history.isLoading || executed.isLoading || expired.isLoading || riskRejected.isLoading
        }
        items={recentHistory}
      />
    </section>
  )
}

// -----------------------------------------------------------------------
// PolicyBanner — KillSwitch + TradingSafety summary
// -----------------------------------------------------------------------

function PolicyBanner() {
  // We don't fetch settings here (no /api/settings/safety endpoint yet).
  // The mutation hooks surface the actual state as 503 + error message
  // once a write is attempted; this static banner is the always-on
  // explainer that points the operator at the gating policy.
  return (
    <div
      data-testid="approvals-policy-banner"
      className="flex items-start gap-3 rounded-lg border border-blue-200 bg-blue-50 p-3 text-sm text-blue-900 dark:border-blue-900/40 dark:bg-blue-900/20 dark:text-blue-200"
    >
      <Activity className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
      <div className="flex flex-col gap-1">
        <p className="font-medium">TRADING_SAFETY + KILL_SWITCH 정책</p>
        <p>
          이 화면은 <code className="rounded bg-blue-100 px-1 py-0.5 dark:bg-blue-900/40">/api/approvals/*</code>{' '}
          전용입니다. <code className="rounded bg-blue-100 px-1 py-0.5 dark:bg-blue-900/40">TRADING_SAFETY_ENABLED=false</code>{' '}
          또는 <code className="rounded bg-blue-100 px-1 py-0.5 dark:bg-blue-900/40">KILL_SWITCH_ENABLED=true</code>{' '}
          상태에서는 모든 mutation 호출이 503 으로 거부됩니다. 승인된 후보는 항상
          SimulationBroker 만 호출하며 실 KIS 주문은 코드 경로 자체에 존재하지 않습니다.
        </p>
      </div>
    </div>
  )
}

// -----------------------------------------------------------------------
// PendingCandidatesTable
// -----------------------------------------------------------------------

function PendingCandidatesTable({
  loading,
  error,
  items,
  onSelect,
  selectedId,
}: {
  loading: boolean
  error: boolean
  items: OrderCandidate[]
  onSelect: (id: number | null) => void
  selectedId: number | null
}) {
  const approve = useApproveCandidate()
  const reject = useRejectCandidate()
  const expire = useExpireCandidate()

  const disabled = isDisabledError(approve.error) || isDisabledError(reject.error) || isDisabledError(expire.error)

  function onApprove(id: number) {
    approve.mutate(id)
  }

  function onReject(id: number) {
    const reason = window.prompt('거절 사유 (256자 이내)')
    if (!reason) return
    reject.mutate({ candidateId: id, reason })
  }

  function onExpire(id: number) {
    expire.mutate(id)
  }

  return (
    <section
      data-testid="approvals-pending-card"
      className="rounded-lg border border-border bg-card p-4"
    >
      <header className="mb-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <ShieldCheck className="h-4 w-4 text-muted-foreground" aria-hidden />
          <h3 className="text-sm font-semibold">승인 대기 후보</h3>
        </div>
        <span data-testid="approvals-pending-count" className="text-xs text-muted-foreground">
          {items.length} 건
        </span>
      </header>
      {loading && (
        <p data-testid="approvals-pending-loading" className="text-sm text-muted-foreground">
          후보 로딩 중…
        </p>
      )}
      {error && (
        <p data-testid="approvals-pending-error" className="text-sm text-red-700 dark:text-red-300">
          후보를 불러오지 못했습니다.
        </p>
      )}
      {!loading && !error && items.length === 0 && (
        <p data-testid="approvals-pending-empty" className="text-sm text-muted-foreground">
          승인 대기중인 후보가 없습니다.
        </p>
      )}
      {items.length > 0 && (
        <div className="overflow-x-auto">
          <table className="w-full text-sm" data-testid="approvals-pending-table">
            <thead>
              <tr className="text-left text-xs text-muted-foreground">
                <th className="px-2 py-1">id</th>
                <th className="px-2 py-1">종목</th>
                <th className="px-2 py-1">방향</th>
                <th className="px-2 py-1 text-right">수량</th>
                <th className="px-2 py-1">유형</th>
                <th className="px-2 py-1 text-right">예상 금액</th>
                <th className="px-2 py-1">출처</th>
                <th className="px-2 py-1">생성</th>
                <th className="px-2 py-1">만료</th>
                <th className="px-2 py-1" />
              </tr>
            </thead>
            <tbody>
              {items.map(c => (
                <tr
                  key={c.id}
                  data-testid={`approvals-row-${c.id}`}
                  className={cn(
                    'border-t border-border/50',
                    selectedId === c.id && 'bg-accent/40',
                  )}
                  onClick={() => onSelect(c.id)}
                >
                  <td className="px-2 py-1">{c.id}</td>
                  <td className="px-2 py-1 font-medium">{c.symbol}</td>
                  <td className="px-2 py-1">{c.side}</td>
                  <td className="px-2 py-1 text-right">{c.quantity}</td>
                  <td className="px-2 py-1">{c.order_type}</td>
                  <td className="px-2 py-1 text-right">{fmtNum(c.estimated_amount)}</td>
                  <td className="px-2 py-1 text-xs text-muted-foreground">{c.source}</td>
                  <td className="px-2 py-1 text-xs text-muted-foreground">{fmtDate(c.created_at)}</td>
                  <td className="px-2 py-1 text-xs text-muted-foreground">{fmtDate(c.expires_at)}</td>
                  <td className="px-2 py-1 text-right whitespace-nowrap">
                    <button
                      data-testid={`approvals-approve-${c.id}`}
                      type="button"
                      onClick={e => {
                        e.stopPropagation()
                        onApprove(c.id)
                      }}
                      disabled={approve.isPending}
                      className="mr-1 rounded border border-input bg-primary px-2 py-0.5 text-xs text-primary-foreground hover:bg-primary/90 disabled:opacity-60"
                    >
                      승인 (paper 실행)
                    </button>
                    <button
                      data-testid={`approvals-reject-${c.id}`}
                      type="button"
                      onClick={e => {
                        e.stopPropagation()
                        onReject(c.id)
                      }}
                      disabled={reject.isPending}
                      className="mr-1 rounded border border-input bg-background px-2 py-0.5 text-xs hover:bg-accent disabled:opacity-60"
                    >
                      거절
                    </button>
                    <button
                      data-testid={`approvals-expire-${c.id}`}
                      type="button"
                      onClick={e => {
                        e.stopPropagation()
                        onExpire(c.id)
                      }}
                      disabled={expire.isPending}
                      className="rounded border border-input bg-background px-2 py-0.5 text-xs hover:bg-accent disabled:opacity-60"
                    >
                      만료
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {disabled && (
        <p
          data-testid="approvals-disabled-banner"
          className="mt-2 flex items-center gap-1 rounded border border-amber-200 bg-amber-50 p-2 text-xs text-amber-800 dark:border-amber-900/40 dark:bg-amber-900/20 dark:text-amber-200"
        >
          <ShieldAlert className="h-3 w-3" aria-hidden />
          승인 워크플로우가 비활성 상태입니다 (TRADING_SAFETY_ENABLED=false 또는
          KILL_SWITCH_ENABLED=true). 운영자가 .env 에서 명시적으로 활성화한 뒤 다시
          시도해 주세요.
        </p>
      )}

      {(isKillSwitchError(approve.error) || isKillSwitchError(reject.error)) && (
        <p
          data-testid="approvals-kill-switch-banner"
          className="mt-2 rounded border border-red-300 bg-red-50 p-2 text-xs text-red-800 dark:border-red-900/40 dark:bg-red-900/20 dark:text-red-200"
        >
          kill switch 가 ON 입니다 — 모든 승인 / 거절 호출이 즉시 거부됩니다.
        </p>
      )}

      {approve.isError && !isDisabledError(approve.error) && (
        <p
          data-testid="approvals-approve-error"
          className="mt-2 rounded border border-red-200 bg-red-50 p-2 text-xs text-red-700 dark:border-red-900/40 dark:bg-red-900/20 dark:text-red-300"
        >
          승인 실패: {approve.error instanceof ApiError ? approve.error.message : '알 수 없는 오류'}
        </p>
      )}

      {approve.isSuccess && approve.data && (
        <p
          data-testid="approvals-approve-success"
          className="mt-2 rounded border border-emerald-200 bg-emerald-50 p-2 text-xs text-emerald-700 dark:border-emerald-900/40 dark:bg-emerald-900/20 dark:text-emerald-200"
        >
          후보 #{approve.data.candidate.id} 가 EXECUTED_PAPER 로 이행, virtual_order_id={
            approve.data.virtual_order_id
          } 가 생성되었습니다.
        </p>
      )}
    </section>
  )
}

// -----------------------------------------------------------------------
// CandidateDetailDrawer — risk_check_result + audit timeline
// -----------------------------------------------------------------------

function CandidateDetailDrawer({
  candidateId,
  onClose,
}: {
  candidateId: number | null
  onClose: () => void
}) {
  const detail = useApprovalCandidate(candidateId)
  const audit = useApprovalAudit(
    candidateId !== null ? { candidateId, limit: 50 } : {},
  )

  if (candidateId === null) return null

  return (
    <section
      data-testid="approvals-detail-drawer"
      className="rounded-lg border border-border bg-card p-4"
    >
      <header className="mb-3 flex items-center justify-between">
        <h3 className="text-sm font-semibold">후보 #{candidateId} 상세</h3>
        <button
          type="button"
          data-testid="approvals-detail-close"
          onClick={onClose}
          className="rounded border border-input bg-background px-2 py-0.5 text-xs hover:bg-accent"
        >
          닫기
        </button>
      </header>
      {detail.isLoading && (
        <p data-testid="approvals-detail-loading" className="text-sm text-muted-foreground">
          상세 로딩 중…
        </p>
      )}
      {detail.isError && (
        <p data-testid="approvals-detail-error" className="text-sm text-red-700 dark:text-red-300">
          상세 정보를 불러오지 못했습니다.
        </p>
      )}
      {detail.data && (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          <CandidateSummary candidate={detail.data.candidate} />
          <RiskCheckPanel risk={detail.data.risk_check_result} />
          <AuditTimeline
            loading={audit.isLoading}
            error={audit.isError}
            items={audit.data?.items ?? []}
          />
        </div>
      )}
    </section>
  )
}

function CandidateSummary({ candidate }: { candidate: OrderCandidate }) {
  return (
    <div data-testid="approvals-detail-summary" className="rounded border border-border/50 p-3 text-sm">
      <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
        후보 요약
      </h4>
      <dl className="grid grid-cols-2 gap-2">
        <Stat label="상태" value={candidate.status} />
        <Stat label="종목" value={candidate.symbol} />
        <Stat label="방향" value={candidate.side} />
        <Stat label="수량" value={String(candidate.quantity)} />
        <Stat label="유형" value={candidate.order_type} />
        <Stat label="지정가" value={fmtNum(candidate.limit_price)} />
        <Stat label="예상 금액" value={fmtNum(candidate.estimated_amount)} />
        <Stat label="출처" value={candidate.source} />
        <Stat label="만료" value={fmtDate(candidate.expires_at)} />
        <Stat label="virtual_order_id" value={candidate.virtual_order_id ?? '—'} />
      </dl>
      {candidate.rejection_reason && (
        <p
          data-testid="approvals-detail-rejection-reason"
          className="mt-2 rounded border border-amber-200 bg-amber-50 p-2 text-xs text-amber-800 dark:border-amber-900/40 dark:bg-amber-900/20 dark:text-amber-200"
        >
          {candidate.rejection_reason}
        </p>
      )}
    </div>
  )
}

function Stat({ label, value }: { label: string; value: string | number }) {
  return (
    <>
      <dt className="text-[10px] uppercase tracking-wide text-muted-foreground">{label}</dt>
      <dd className="text-sm font-medium">{value}</dd>
    </>
  )
}

function RiskCheckPanel({ risk }: { risk: RiskCheckResult | null }) {
  return (
    <div data-testid="approvals-detail-risk" className="rounded border border-border/50 p-3 text-sm">
      <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
        Risk 체크 결과
      </h4>
      {!risk && (
        <p data-testid="approvals-detail-risk-empty" className="text-xs text-muted-foreground">
          아직 위험 평가 결과가 없습니다.
        </p>
      )}
      {risk && (
        <>
          <p className="mb-2 text-xs">
            <span className="text-muted-foreground">policy_version:</span>{' '}
            <code className="rounded bg-muted px-1">{risk.policy_version}</code>
            {' · '}
            <span className="text-muted-foreground">passed:</span>{' '}
            <strong
              className={cn(
                'rounded px-1.5 py-0.5 text-[10px]',
                risk.passed
                  ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-200'
                  : 'bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-200',
              )}
            >
              {risk.passed ? 'PASS' : 'FAIL'}
            </strong>
          </p>
          {risk.violations.length === 0 ? (
            <p className="text-xs text-muted-foreground">위반 사항 없음.</p>
          ) : (
            <ul className="space-y-1 text-xs">
              {risk.violations.map((v, idx) => (
                <li
                  key={`${v.rule_id}-${idx}`}
                  data-testid={`approvals-detail-violation-${v.rule_id}`}
                  className="rounded border border-red-200 bg-red-50 px-2 py-1 text-red-800 dark:border-red-900/40 dark:bg-red-900/20 dark:text-red-200"
                >
                  <span className="font-medium">{v.rule_id}</span>{' · '}
                  <span>{v.message}</span>
                </li>
              ))}
            </ul>
          )}
        </>
      )}
    </div>
  )
}

function AuditTimeline({
  loading,
  error,
  items,
}: {
  loading: boolean
  error: boolean
  items: ApprovalAuditLogItem[]
}) {
  return (
    <div
      data-testid="approvals-detail-audit"
      className="rounded border border-border/50 p-3 text-sm lg:col-span-2"
    >
      <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
        감사 이력 (append-only)
      </h4>
      {loading && <p className="text-xs text-muted-foreground">audit 로딩 중…</p>}
      {error && (
        <p className="text-xs text-red-700 dark:text-red-300">audit 를 불러오지 못했습니다.</p>
      )}
      {!loading && !error && items.length === 0 && (
        <p
          data-testid="approvals-detail-audit-empty"
          className="text-xs text-muted-foreground"
        >
          이 후보에 대한 audit 행이 아직 없습니다.
        </p>
      )}
      {items.length > 0 && (
        <ol className="space-y-1 text-xs">
          {items.map(row => (
            <li
              key={row.id}
              data-testid={`approvals-audit-row-${row.id}`}
              className="flex items-center gap-2 rounded border border-border/30 px-2 py-1"
            >
              <span className="font-mono text-[10px] text-muted-foreground">
                {fmtDate(row.created_at)}
              </span>
              <span className="rounded bg-muted px-1.5 py-0.5 text-[10px] font-medium">
                {row.event_type}
              </span>
              {row.reason && <span className="text-muted-foreground">{row.reason}</span>}
            </li>
          ))}
        </ol>
      )}
    </div>
  )
}

// -----------------------------------------------------------------------
// NewCandidateForm — manual candidate creation
// -----------------------------------------------------------------------

function NewCandidateForm() {
  const submit = useSubmitApprovalCandidate()
  const [symbol, setSymbol] = useState('')
  const [side, setSide] = useState<'BUY' | 'SELL'>('BUY')
  const [orderType, setOrderType] = useState<'MARKET' | 'LIMIT'>('MARKET')
  const [quantity, setQuantity] = useState('')
  const [limitPrice, setLimitPrice] = useState('')
  const [estimated, setEstimated] = useState('')

  const disabled = isDisabledError(submit.error)

  function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!symbol.trim() || !quantity.trim()) return
    const qty = Number(quantity)
    if (!Number.isInteger(qty) || qty <= 0) return
    submit.mutate(
      {
        symbol: symbol.trim().toUpperCase(),
        side,
        quantity: qty,
        order_type: orderType,
        limit_price: orderType === 'LIMIT' ? limitPrice.trim() || null : null,
        estimated_amount: estimated.trim() || null,
        source: 'MANUAL',
      },
      {
        onSuccess: () => {
          setSymbol('')
          setQuantity('')
          setLimitPrice('')
          setEstimated('')
        },
      },
    )
  }

  return (
    <form
      data-testid="approvals-new-form"
      onSubmit={onSubmit}
      className="flex flex-col gap-3 rounded-lg border border-border bg-card p-4"
    >
      <div className="flex items-center gap-2">
        <ShieldCheck className="h-4 w-4 text-muted-foreground" aria-hidden />
        <h3 className="text-sm font-semibold">새 후보 (수동 생성, paper)</h3>
      </div>

      <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
        <label className="flex flex-col gap-1 text-xs">
          <span className="text-muted-foreground">종목 코드</span>
          <input
            data-testid="approvals-new-symbol-input"
            value={symbol}
            onChange={e => setSymbol(e.target.value)}
            placeholder="005930"
            maxLength={32}
            className="rounded-md border border-input bg-background px-2 py-1 text-sm"
          />
        </label>
        <label className="flex flex-col gap-1 text-xs">
          <span className="text-muted-foreground">방향</span>
          <select
            data-testid="approvals-new-side-select"
            value={side}
            onChange={e => setSide(e.target.value as 'BUY' | 'SELL')}
            className="rounded-md border border-input bg-background px-2 py-1 text-sm"
          >
            <option value="BUY">BUY</option>
            <option value="SELL">SELL</option>
          </select>
        </label>
        <label className="flex flex-col gap-1 text-xs">
          <span className="text-muted-foreground">유형</span>
          <select
            data-testid="approvals-new-type-select"
            value={orderType}
            onChange={e => setOrderType(e.target.value as 'MARKET' | 'LIMIT')}
            className="rounded-md border border-input bg-background px-2 py-1 text-sm"
          >
            <option value="MARKET">MARKET</option>
            <option value="LIMIT">LIMIT</option>
          </select>
        </label>

        <label className="flex flex-col gap-1 text-xs">
          <span className="text-muted-foreground">수량 (주)</span>
          <input
            data-testid="approvals-new-quantity-input"
            value={quantity}
            onChange={e => setQuantity(e.target.value)}
            inputMode="numeric"
            placeholder="10"
            className="rounded-md border border-input bg-background px-2 py-1 text-sm"
          />
        </label>
        {orderType === 'LIMIT' && (
          <label className="flex flex-col gap-1 text-xs">
            <span className="text-muted-foreground">지정가</span>
            <input
              data-testid="approvals-new-limit-price-input"
              value={limitPrice}
              onChange={e => setLimitPrice(e.target.value)}
              inputMode="decimal"
              placeholder="71000"
              className="rounded-md border border-input bg-background px-2 py-1 text-sm"
            />
          </label>
        )}
        <label className="flex flex-col gap-1 text-xs">
          <span className="text-muted-foreground">예상 금액</span>
          <input
            data-testid="approvals-new-estimated-input"
            value={estimated}
            onChange={e => setEstimated(e.target.value)}
            inputMode="decimal"
            placeholder="100000"
            className="rounded-md border border-input bg-background px-2 py-1 text-sm"
          />
        </label>
      </div>

      <button
        type="submit"
        data-testid="approvals-new-submit"
        disabled={submit.isPending}
        className={cn(
          'inline-flex items-center justify-center gap-2 rounded-md border border-input bg-primary px-3 py-2 text-sm font-medium text-primary-foreground transition-colors',
          'hover:bg-primary/90',
          'disabled:cursor-not-allowed disabled:opacity-60',
        )}
      >
        후보 만들기 (Risk Check)
      </button>

      {submit.isSuccess && submit.data && (
        <p
          data-testid="approvals-new-success"
          className="rounded border border-emerald-200 bg-emerald-50 p-2 text-xs text-emerald-700 dark:border-emerald-900/40 dark:bg-emerald-900/20 dark:text-emerald-200"
        >
          후보 #{submit.data.candidate.id} 생성 — 상태 {submit.data.candidate.status}
          {submit.data.risk_passed ? '' : ' (risk 룰 위반)'}
        </p>
      )}

      {disabled && (
        <p
          data-testid="approvals-new-disabled-banner"
          className="flex items-center gap-1 rounded border border-amber-200 bg-amber-50 p-2 text-xs text-amber-800 dark:border-amber-900/40 dark:bg-amber-900/20 dark:text-amber-200"
        >
          <ShieldAlert className="h-3 w-3" aria-hidden />
          승인 워크플로우가 비활성 상태입니다 — 운영자가 .env 에서 명시적으로
          활성화한 뒤 다시 시도해 주세요.
        </p>
      )}

      {submit.isError && !disabled && (
        <p
          data-testid="approvals-new-error"
          className="rounded border border-red-200 bg-red-50 p-2 text-xs text-red-700 dark:border-red-900/40 dark:bg-red-900/20 dark:text-red-300"
        >
          후보 생성 실패: {submit.error instanceof ApiError ? submit.error.message : '알 수 없는 오류'}
        </p>
      )}
    </form>
  )
}

// -----------------------------------------------------------------------
// HistoryTable — recent terminal candidates
// -----------------------------------------------------------------------

function HistoryTable({
  loading,
  items,
}: {
  loading: boolean
  items: OrderCandidate[]
}) {
  return (
    <section
      data-testid="approvals-history-card"
      className="rounded-lg border border-border bg-card p-4"
    >
      <header className="mb-3 flex items-center justify-between">
        <h3 className="text-sm font-semibold">최근 결정 이력 ({items.length})</h3>
      </header>
      {loading && (
        <p data-testid="approvals-history-loading" className="text-sm text-muted-foreground">
          이력 로딩 중…
        </p>
      )}
      {!loading && items.length === 0 && (
        <p data-testid="approvals-history-empty" className="text-sm text-muted-foreground">
          아직 종결된 후보가 없습니다.
        </p>
      )}
      {items.length > 0 && (
        <div className="overflow-x-auto">
          <table className="w-full text-sm" data-testid="approvals-history-table">
            <thead>
              <tr className="text-left text-xs text-muted-foreground">
                <th className="px-2 py-1">id</th>
                <th className="px-2 py-1">종목</th>
                <th className="px-2 py-1">방향</th>
                <th className="px-2 py-1 text-right">수량</th>
                <th className="px-2 py-1">상태</th>
                <th className="px-2 py-1">사유</th>
                <th className="px-2 py-1">갱신</th>
              </tr>
            </thead>
            <tbody>
              {items.map(c => {
                const terminal = TERMINAL_STATUSES.has(c.status)
                return (
                  <tr
                    key={c.id}
                    data-testid={`approvals-history-row-${c.id}`}
                    className="border-t border-border/50"
                  >
                    <td className="px-2 py-1">{c.id}</td>
                    <td className="px-2 py-1 font-medium">{c.symbol}</td>
                    <td className="px-2 py-1">{c.side}</td>
                    <td className="px-2 py-1 text-right">{c.quantity}</td>
                    <td
                      className={cn(
                        'px-2 py-1 text-xs',
                        c.status === 'EXECUTED_PAPER' &&
                          'text-emerald-700 dark:text-emerald-200',
                        c.status === 'REJECTED' &&
                          'text-red-700 dark:text-red-200',
                        c.status === 'EXPIRED' && 'text-muted-foreground',
                        c.status === 'RISK_REJECTED' &&
                          'text-amber-700 dark:text-amber-200',
                      )}
                    >
                      {c.status}
                      {terminal ? '' : ' (in-flight)'}
                    </td>
                    <td className="px-2 py-1 text-xs text-muted-foreground">
                      {c.rejection_reason ?? '—'}
                    </td>
                    <td className="px-2 py-1 text-xs text-muted-foreground">
                      {fmtDate(c.updated_at)}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}
