// v0.16 Phase E — Real Orders dashboard (/real-orders).
//
// Hard policies enforced by this page:
//   - Calls go ONLY to /api/real-orders/* (GET only, read-only).
//   - NEVER shows a button labelled "실주문 실행" / "주문 전송" /
//     "place real order" / "자동매매" / "FULL_AUTO" / "SMALL_AUTO".
//   - Forbidden response fields are NEVER rendered:
//       broker_order_no_hash / api_key / app_secret / access_token /
//       token / secret / raw_response / account_number / real_account.
//   - All dry-run records show a DRY_RUN badge; users can see the
//     execution was simulated, not real.
//   - Safety banner is always visible at the top.

import { useState } from 'react'
import { ShieldAlert, TrendingUp } from 'lucide-react'
import { cn } from '@/lib/utils'
import { useRealOrderDetail, useRealOrders } from '@/hooks/useRealOrders'
import type { RealFill, RealOrder, RealOrderStatus } from '@/api/types'

// ---------------------------------------------------------------------------
// Utilities
// ---------------------------------------------------------------------------

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
  return num.toLocaleString('ko-KR', { maximumFractionDigits: 4, minimumFractionDigits: 0 })
}

const STATUS_COLORS: Record<string, string> = {
  DRY_RUN: 'bg-blue-100 text-blue-800',
  CREATED: 'bg-gray-100 text-gray-700',
  SUBMITTED: 'bg-yellow-100 text-yellow-800',
  PARTIALLY_FILLED: 'bg-orange-100 text-orange-800',
  FILLED: 'bg-green-100 text-green-800',
  CANCELED: 'bg-gray-200 text-gray-600',
  REJECTED: 'bg-red-100 text-red-700',
  FAILED: 'bg-red-200 text-red-800',
}

function StatusBadge({ status }: { status: RealOrderStatus }) {
  return (
    <span
      className={cn(
        'inline-flex items-center rounded px-2 py-0.5 text-xs font-semibold',
        STATUS_COLORS[status] ?? 'bg-gray-100 text-gray-700',
      )}
    >
      {status}
    </span>
  )
}

// ---------------------------------------------------------------------------
// Safety banner (always visible)
// ---------------------------------------------------------------------------

function RealTradingSafetyBanner() {
  return (
    <div
      className="flex items-start gap-3 rounded-lg border border-blue-200 bg-blue-50 p-4"
      data-testid="real-orders-safety-banner"
    >
      <ShieldAlert className="mt-0.5 h-5 w-5 shrink-0 text-blue-600" />
      <div className="text-sm text-blue-900">
        <p className="font-semibold">현재 화면은 dry-run / 기록 조회 전용입니다.</p>
        <p className="mt-1">
          실제 KIS 주문은 실행되지 않습니다. 모든 기록은{' '}
          <span className="font-medium">FakeKisOrderTransport</span>를 통해 생성된{' '}
          <StatusBadge status="DRY_RUN" />
          &nbsp;시뮬레이션 데이터입니다.
        </p>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Summary cards
// ---------------------------------------------------------------------------

function SummaryCard({
  label,
  value,
  testId,
}: {
  label: string
  value: number | string
  testId: string
}) {
  return (
    <div
      className="flex flex-col gap-1 rounded-lg border bg-card p-4"
      data-testid={testId}
    >
      <span className="text-xs text-muted-foreground">{label}</span>
      <span className="text-2xl font-semibold">{value}</span>
    </div>
  )
}

function RealOrderSummaryCards({ orders }: { orders: RealOrder[] }) {
  const dryRunCount = orders.filter(o => o.status === 'DRY_RUN').length
  const filledCount = orders.filter(o => o.status === 'FILLED').length
  return (
    <div
      className="grid grid-cols-3 gap-3"
      data-testid="real-orders-summary-cards"
    >
      <SummaryCard label="총 주문 수" value={orders.length} testId="real-orders-total-card" />
      <SummaryCard label="Dry-run" value={dryRunCount} testId="real-orders-dryrun-card" />
      <SummaryCard label="체결 완료" value={filledCount} testId="real-orders-filled-card" />
    </div>
  )
}

// ---------------------------------------------------------------------------
// Orders table
// ---------------------------------------------------------------------------

function RealOrdersTable({
  orders,
  selectedId,
  onSelect,
}: {
  orders: RealOrder[]
  selectedId: number | null
  onSelect: (id: number) => void
}) {
  if (orders.length === 0) {
    return (
      <div
        className="rounded-lg border bg-card p-8 text-center text-sm text-muted-foreground"
        data-testid="real-orders-empty"
      >
        dry-run 실행 기록이 없습니다. RealOrderExecutor를 실행하면 여기에 표시됩니다.
      </div>
    )
  }

  return (
    <div
      className="overflow-x-auto rounded-lg border bg-card"
      data-testid="real-orders-table"
    >
      <table className="w-full text-sm">
        <thead className="border-b bg-muted/40">
          <tr>
            <th className="px-3 py-2 text-left font-medium text-muted-foreground">ID</th>
            <th className="px-3 py-2 text-left font-medium text-muted-foreground">종목</th>
            <th className="px-3 py-2 text-left font-medium text-muted-foreground">매매</th>
            <th className="px-3 py-2 text-right font-medium text-muted-foreground">수량</th>
            <th className="px-3 py-2 text-left font-medium text-muted-foreground">유형</th>
            <th className="px-3 py-2 text-right font-medium text-muted-foreground">예상금액</th>
            <th className="px-3 py-2 text-left font-medium text-muted-foreground">상태</th>
            <th className="px-3 py-2 text-left font-medium text-muted-foreground">생성일시</th>
          </tr>
        </thead>
        <tbody className="divide-y">
          {orders.map(order => (
            <tr
              key={order.id}
              className={cn(
                'cursor-pointer transition-colors hover:bg-accent/50',
                selectedId === order.id && 'bg-accent',
              )}
              onClick={() => onSelect(order.id)}
              data-testid={`real-order-row-${order.id}`}
            >
              <td className="px-3 py-2 font-mono text-xs">{order.id}</td>
              <td className="px-3 py-2 font-medium">{order.symbol}</td>
              <td className="px-3 py-2">
                <span
                  className={cn(
                    'text-xs font-semibold',
                    order.side === 'BUY' ? 'text-red-600' : 'text-blue-600',
                  )}
                >
                  {order.side}
                </span>
              </td>
              <td className="px-3 py-2 text-right">{order.quantity.toLocaleString('ko-KR')}</td>
              <td className="px-3 py-2 text-muted-foreground">{order.order_type}</td>
              <td className="px-3 py-2 text-right">{fmtNum(order.estimated_amount)}</td>
              <td className="px-3 py-2">
                <StatusBadge status={order.status} />
              </td>
              <td className="px-3 py-2 text-muted-foreground">{fmtDate(order.created_at)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Fills table (inside detail panel)
// ---------------------------------------------------------------------------

function RealFillsTable({ fills }: { fills: RealFill[] }) {
  if (fills.length === 0) {
    return (
      <p
        className="text-sm text-muted-foreground"
        data-testid="real-fills-empty"
      >
        체결 기록이 없습니다.
      </p>
    )
  }
  return (
    <div className="overflow-x-auto rounded-lg border" data-testid="real-fills-table">
      <table className="w-full text-sm">
        <thead className="border-b bg-muted/40">
          <tr>
            <th className="px-3 py-2 text-left font-medium text-muted-foreground">ID</th>
            <th className="px-3 py-2 text-right font-medium text-muted-foreground">수량</th>
            <th className="px-3 py-2 text-right font-medium text-muted-foreground">체결가</th>
            <th className="px-3 py-2 text-right font-medium text-muted-foreground">총액</th>
            <th className="px-3 py-2 text-left font-medium text-muted-foreground">구분</th>
            <th className="px-3 py-2 text-left font-medium text-muted-foreground">체결시각</th>
          </tr>
        </thead>
        <tbody className="divide-y">
          {fills.map(fill => (
            <tr key={fill.id} data-testid={`real-fill-row-${fill.id}`}>
              <td className="px-3 py-2 font-mono text-xs">{fill.id}</td>
              <td className="px-3 py-2 text-right">{fill.quantity.toLocaleString('ko-KR')}</td>
              <td className="px-3 py-2 text-right">{fmtNum(fill.fill_price)}</td>
              <td className="px-3 py-2 text-right">{fmtNum(fill.gross_amount)}</td>
              <td className="px-3 py-2">
                <span
                  className={cn(
                    'rounded px-1.5 py-0.5 text-xs font-medium',
                    fill.fill_status === 'FULL'
                      ? 'bg-green-100 text-green-800'
                      : 'bg-orange-100 text-orange-800',
                  )}
                >
                  {fill.fill_status}
                </span>
              </td>
              <td className="px-3 py-2 text-muted-foreground">{fmtDate(fill.filled_at)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Order detail panel
// ---------------------------------------------------------------------------

function RealOrderDetailPanel({
  orderId,
  onClose,
}: {
  orderId: number
  onClose: () => void
}) {
  const { data, isLoading, isError } = useRealOrderDetail(orderId)

  return (
    <div
      className="flex flex-col gap-4 rounded-lg border bg-card p-5"
      data-testid="real-orders-detail"
    >
      <div className="flex items-center justify-between">
        <h3 className="font-semibold">주문 상세 #{orderId}</h3>
        <button
          type="button"
          onClick={onClose}
          className="rounded px-2 py-1 text-xs text-muted-foreground hover:bg-accent"
        >
          닫기
        </button>
      </div>

      {isLoading && (
        <p className="text-sm text-muted-foreground">불러오는 중…</p>
      )}
      {isError && (
        <p className="text-sm text-red-600">상세 정보를 불러올 수 없습니다.</p>
      )}
      {data && (
        <>
          <section className="grid grid-cols-2 gap-2 text-sm">
            <div>
              <span className="text-muted-foreground">종목:</span>{' '}
              <strong>{data.order.symbol}</strong>
            </div>
            <div>
              <span className="text-muted-foreground">매매:</span>{' '}
              <strong
                className={
                  data.order.side === 'BUY' ? 'text-red-600' : 'text-blue-600'
                }
              >
                {data.order.side}
              </strong>
            </div>
            <div>
              <span className="text-muted-foreground">수량:</span>{' '}
              {data.order.quantity.toLocaleString('ko-KR')}
            </div>
            <div>
              <span className="text-muted-foreground">유형:</span> {data.order.order_type}
            </div>
            <div>
              <span className="text-muted-foreground">예상금액:</span>{' '}
              {fmtNum(data.order.estimated_amount)}
            </div>
            <div>
              <span className="text-muted-foreground">상태:</span>{' '}
              <StatusBadge status={data.order.status} />
            </div>
            <div>
              <span className="text-muted-foreground">Dry-run:</span>{' '}
              {data.order.dry_run ? '예' : '아니오'}
            </div>
            <div>
              <span className="text-muted-foreground">Fake 주문번호:</span>{' '}
              <span className="font-mono text-xs">{data.order.fake_order_no ?? '—'}</span>
            </div>
            {data.order.error_code && (
              <div className="col-span-2 rounded bg-red-50 p-2 text-xs text-red-700">
                오류: [{data.order.error_code}] {data.order.error_message}
              </div>
            )}
            <div className="col-span-2">
              <span className="text-muted-foreground">생성일시:</span>{' '}
              {fmtDate(data.order.created_at)}
            </div>
          </section>

          <section>
            <h4 className="mb-2 text-sm font-semibold text-muted-foreground">
              체결 내역 ({data.fills.length}건)
            </h4>
            <RealFillsTable fills={data.fills} />
          </section>
        </>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Page root
// ---------------------------------------------------------------------------

export function RealOrdersPage() {
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const { data, isLoading, isError } = useRealOrders({ limit: 100 })

  const orders = data?.items ?? []

  return (
    <section className="flex flex-col gap-4" data-testid="real-orders-page">
      <header className="flex flex-wrap items-end justify-between gap-2">
        <div>
          <h2 className="text-2xl font-semibold">실주문 준비 (β)</h2>
          <p className="mt-0.5 text-sm text-muted-foreground">
            Dry-run 실행 기록 · 체결 내역 조회 전용 — 실 KIS 주문 0건
          </p>
        </div>
        <TrendingUp className="h-6 w-6 text-muted-foreground" />
      </header>

      <RealTradingSafetyBanner />

      {isLoading && (
        <p className="text-sm text-muted-foreground" data-testid="real-orders-loading">
          주문 기록을 불러오는 중…
        </p>
      )}

      {isError && (
        <div
          className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700"
          data-testid="real-orders-error"
        >
          주문 기록을 불러올 수 없습니다. 잠시 후 다시 시도해 주세요.
        </div>
      )}

      {!isLoading && !isError && (
        <>
          <RealOrderSummaryCards orders={orders} />
          <RealOrdersTable
            orders={orders}
            selectedId={selectedId}
            onSelect={id => setSelectedId(id === selectedId ? null : id)}
          />
          {selectedId !== null && (
            <RealOrderDetailPanel
              orderId={selectedId}
              onClose={() => setSelectedId(null)}
            />
          )}
        </>
      )}
    </section>
  )
}
