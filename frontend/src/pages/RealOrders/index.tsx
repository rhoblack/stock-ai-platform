// v0.16 Phase E — Real Orders dashboard (/real-orders).
// v1.0 Phase E — adds RealTradingModeBanner + manual Sync Fill button.
//
// Hard policies enforced by this page:
//   - Calls go ONLY to /api/real-orders/* — GET (read-only) and the SOLE
//     mutation POST /api/real-orders/{id}/sync (manual fill sync).
//   - NEVER shows a button labelled "실주문 실행" / "주문 전송" /
//     "place real order" / "자동매매" / "FULL_AUTO" / "SMALL_AUTO".
//   - Forbidden response fields are NEVER rendered:
//       broker_order_no_hash / broker_order_no / api_key / app_secret /
//       access_token / token / secret / raw_response / account_number /
//       real_account.
//   - All dry-run records show a DRY_RUN badge; users can see the
//     execution was simulated, not real.
//   - RealTradingModeBanner reflects 5 bool flags from /api/settings:
//       trading_safety_enabled / kill_switch_enabled / real_trading_enabled /
//       kis_order_enabled / real_order_dry_run.
//   - Sync Fill button is disabled when:
//       order.dry_run === true (DRY_RUN orders skip transport per Phase D)
//       OR settings.kill_switch_enabled === true
//       OR settings.trading_safety_enabled === false
//       OR order.status is in a terminal state (FILLED / CANCELED / REJECTED / FAILED)

import { useState } from 'react'
import { ShieldAlert, TrendingUp, RefreshCw } from 'lucide-react'
import { cn } from '@/lib/utils'
import {
  useRealOrderDetail,
  useRealOrders,
  useSyncRealOrder,
} from '@/hooks/useRealOrders'
import { useSettings } from '@/hooks/useSettings'
import type {
  RealFill,
  RealOrder,
  RealOrderStatus,
  SettingsResponse,
} from '@/api/types'

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

const TERMINAL_STATUSES: ReadonlySet<RealOrderStatus> = new Set([
  'FILLED',
  'CANCELED',
  'REJECTED',
  'FAILED',
])

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
// v1.0 Phase E — Real trading mode banner
// ---------------------------------------------------------------------------
//
// Replaces the v0.16 RealTradingSafetyBanner with a settings-aware banner
// that surfaces the live values of the 5 safety bool flags. Operators read
// this to verify the system is in dry-run / real-trading-enabled / paranoid
// state at a glance.

interface SafetyFlags {
  trading_safety_enabled: boolean
  kill_switch_enabled: boolean
  real_trading_enabled: boolean
  kis_order_enabled: boolean
  real_order_dry_run: boolean
}

function _flagsFromSettings(s: SettingsResponse | undefined): SafetyFlags {
  return {
    trading_safety_enabled: s?.trading_safety_enabled ?? false,
    kill_switch_enabled: s?.kill_switch_enabled ?? true,
    real_trading_enabled: s?.real_trading_enabled ?? false,
    kis_order_enabled: s?.kis_order_enabled ?? false,
    real_order_dry_run: s?.real_order_dry_run ?? true,
  }
}

function _modeFromFlags(f: SafetyFlags): 'DRY_RUN' | 'REAL' | 'BLOCKED' | 'TRANSITION' {
  if (f.kill_switch_enabled) return 'BLOCKED'
  if (!f.trading_safety_enabled) return 'BLOCKED'
  if (f.real_order_dry_run) return 'DRY_RUN'
  if (f.real_trading_enabled && f.kis_order_enabled) return 'REAL'
  return 'TRANSITION'
}

function _modeBadgeClasses(mode: ReturnType<typeof _modeFromFlags>): string {
  switch (mode) {
    case 'REAL':
      return 'bg-red-100 text-red-800 border-red-200'
    case 'DRY_RUN':
      return 'bg-blue-100 text-blue-800 border-blue-200'
    case 'BLOCKED':
      return 'bg-amber-100 text-amber-800 border-amber-200'
    case 'TRANSITION':
      return 'bg-yellow-100 text-yellow-800 border-yellow-200'
  }
}

function _modeLabel(mode: ReturnType<typeof _modeFromFlags>): string {
  switch (mode) {
    case 'REAL':
      return 'REAL TRADING ENABLED'
    case 'DRY_RUN':
      return 'DRY-RUN'
    case 'BLOCKED':
      return 'KILL SWITCH ON'
    case 'TRANSITION':
      return '전이 상태 (게이트 일부 미충족)'
  }
}

function _modeMessage(mode: ReturnType<typeof _modeFromFlags>): string {
  switch (mode) {
    case 'REAL':
      return (
        '실 KIS 주문이 활성화된 상태입니다. 사용자 명시 승인된 후보만 실 주문으로 진입합니다.'
      )
    case 'DRY_RUN':
      return (
        '모든 실행은 dry-run 입니다. 실제 KIS 주문은 발생하지 않습니다.'
      )
    case 'BLOCKED':
      return (
        'kill switch 또는 trading safety 게이트가 닫혀 있어 실거래가 차단된 상태입니다.'
      )
    case 'TRANSITION':
      return (
        '실거래 활성화 전제 조건 일부가 미충족 상태입니다. RUNBOOK §2 활성화 절차를 확인하세요.'
      )
  }
}

function FlagBadge({
  label,
  active,
  truthIsSafer,
}: {
  label: string
  active: boolean
  // When ``true``, the SAFER state is when the flag is ``true`` (e.g. kill_switch).
  // When ``false``, the SAFER state is when the flag is ``false`` (e.g. real_trading).
  truthIsSafer: boolean
}) {
  const isSafe = truthIsSafer ? active : !active
  return (
    <span
      data-testid={`real-trading-flag-${label}`}
      className={cn(
        'inline-flex items-center gap-1 rounded border px-2 py-0.5 text-xs font-mono',
        isSafe
          ? 'border-emerald-200 bg-emerald-50 text-emerald-800'
          : 'border-red-200 bg-red-50 text-red-800',
      )}
    >
      <span className="font-semibold">{label}</span>
      <span>=</span>
      <span>{active ? 'true' : 'false'}</span>
    </span>
  )
}

function RealTradingModeBanner() {
  const { data: settings } = useSettings()
  const flags = _flagsFromSettings(settings)
  const mode = _modeFromFlags(flags)
  return (
    <div
      className={cn(
        'flex flex-col gap-2 rounded-lg border p-4',
        'border-blue-200 bg-blue-50 text-blue-900',
      )}
      data-testid="real-orders-safety-banner"
    >
      <div className="flex items-start gap-3">
        <ShieldAlert className="mt-0.5 h-5 w-5 shrink-0 text-blue-600" />
        <div className="flex-1">
          <div className="flex items-center gap-2 text-sm">
            <span className="font-semibold">실거래 상태:</span>
            <span
              data-testid="real-trading-mode-badge"
              className={cn(
                'inline-flex items-center rounded border px-2 py-0.5 text-xs font-bold',
                _modeBadgeClasses(mode),
              )}
            >
              {_modeLabel(mode)}
            </span>
          </div>
          <p className="mt-1 text-sm">{_modeMessage(mode)}</p>
          <p className="mt-1 text-xs text-blue-800">
            DRY-RUN 모드에서는 실제 KIS 주문이 실행되지 않습니다 — 모든 기록은{' '}
            <span className="font-medium">FakeKisOrderTransport</span>를 통해 생성된
            시뮬레이션 데이터입니다.
          </p>
        </div>
      </div>
      <div
        className="flex flex-wrap items-center gap-1"
        data-testid="real-trading-flags"
      >
        <FlagBadge
          label="TRADING_SAFETY_ENABLED"
          active={flags.trading_safety_enabled}
          truthIsSafer={true}
        />
        <FlagBadge
          label="KILL_SWITCH_ENABLED"
          active={flags.kill_switch_enabled}
          truthIsSafer={false}
        />
        <FlagBadge
          label="REAL_TRADING_ENABLED"
          active={flags.real_trading_enabled}
          truthIsSafer={false}
        />
        <FlagBadge
          label="KIS_ORDER_ENABLED"
          active={flags.kis_order_enabled}
          truthIsSafer={false}
        />
        <FlagBadge
          label="REAL_ORDER_DRY_RUN"
          active={flags.real_order_dry_run}
          truthIsSafer={true}
        />
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
        실행 기록이 없습니다. RealOrderExecutor를 실행하면 여기에 표시됩니다.
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
// v1.0 Phase E — Sync Fill button
// ---------------------------------------------------------------------------
//
// Disabled conditions:
//   - order.dry_run === true (DRY_RUN orders skip transport per Phase D policy)
//   - settings.kill_switch_enabled === true (mutation gate)
//   - settings.trading_safety_enabled === false (mutation gate)
//   - order.status ∈ {FILLED, CANCELED, REJECTED, FAILED} (terminal at our side)
// Mutation in flight → button shows spinner + disabled.

function _syncDisabledReason(
  order: RealOrder,
  flags: SafetyFlags,
): string | null {
  if (order.dry_run) {
    return 'DRY_RUN 주문은 transport 호출 없이 skip 됩니다 (Phase D 정책).'
  }
  if (flags.kill_switch_enabled) {
    return 'KILL_SWITCH_ENABLED=true 상태에서는 sync 가 차단됩니다.'
  }
  if (!flags.trading_safety_enabled) {
    return 'TRADING_SAFETY_ENABLED=false 상태에서는 sync 가 차단됩니다.'
  }
  if (TERMINAL_STATUSES.has(order.status)) {
    return `이미 terminal 상태 (${order.status}) — sync 가 불필요합니다.`
  }
  return null
}

function SyncFillButton({ order }: { order: RealOrder }) {
  const { data: settings } = useSettings()
  const flags = _flagsFromSettings(settings)
  const syncMutation = useSyncRealOrder()
  const disabledReason = _syncDisabledReason(order, flags)
  const isPending = syncMutation.isPending
  const disabled = isPending || disabledReason !== null

  const handleClick = () => {
    if (disabled) return
    syncMutation.mutate({ orderId: order.id })
  }

  // Note: button label NEVER uses "place real order" / "주문 전송" /
  // "실주문 실행" / "자동매매" / "FULL_AUTO" / "SMALL_AUTO". The label is
  // strictly limited to "체결 동기화" (Sync Fill).
  return (
    <div className="flex flex-col gap-1" data-testid="real-order-sync-control">
      <button
        type="button"
        onClick={handleClick}
        disabled={disabled}
        data-testid="real-order-sync-button"
        aria-disabled={disabled}
        className={cn(
          'inline-flex items-center gap-2 rounded-md border px-3 py-1.5 text-sm font-medium transition-colors',
          disabled
            ? 'cursor-not-allowed border-gray-200 bg-gray-50 text-gray-400'
            : 'border-blue-200 bg-blue-50 text-blue-800 hover:bg-blue-100',
        )}
      >
        <RefreshCw
          className={cn('h-4 w-4', isPending && 'animate-spin')}
          aria-hidden
        />
        <span>{isPending ? '동기화 중…' : '체결 동기화'}</span>
      </button>
      {disabledReason && (
        <p
          className="text-xs text-muted-foreground"
          data-testid="real-order-sync-disabled-reason"
        >
          {disabledReason}
        </p>
      )}
      {syncMutation.isError && (
        <p
          className="text-xs text-red-700"
          data-testid="real-order-sync-error"
        >
          체결 동기화 실패 — 잠시 후 다시 시도하거나 RUNBOOK §6 절차를 확인하세요.
        </p>
      )}
      {syncMutation.isSuccess && syncMutation.data && (
        <p
          className="text-xs text-emerald-700"
          data-testid="real-order-sync-success"
        >
          {syncMutation.data.message}
        </p>
      )}
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
            <SyncFillButton order={data.order} />
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
            실행 기록 · 체결 내역 조회 · 수동 체결 동기화 — 사용자 명시 승인된 후보만 진입
          </p>
        </div>
        <TrendingUp className="h-6 w-6 text-muted-foreground" />
      </header>

      <RealTradingModeBanner />

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
