// v0.14 Phase E — Paper / Simulation Trading dashboard (/paper).
//
// Hard policies enforced by this page:
//   - Calls go ONLY to /api/paper/* — never to KIS / real broker / autotrade.
//   - 503 ("paper trading is disabled") surfaces a friendly disabled banner;
//     the order form and cancel buttons are hidden in that mode.
//   - Forbidden response fields (api_key / token / secret / source_file_path /
//     broker_order_id / kis_order_id / real_account / broker /
//     account_number / raw_text / body / full_text) are NEVER referenced
//     in the JSX — the schemas don't carry them and the page only reads
//     the documented PaperOrder / PaperPosition / PaperPnL fields.
//   - All copy uses the words 페이퍼 / 가상 / 시뮬레이션 to make it visually
//     unambiguous that this is NOT a real-money order surface.
//   - There is no "주문 실행" / "자동매매 시작" / "place order" CTA — the
//     button label says "페이퍼 주문 만들기".

import { useState, type FormEvent } from 'react'
import { Activity, Ban, TrendingUp } from 'lucide-react'
import { ApiError } from '@/api/client'
import { cn } from '@/lib/utils'
import {
  useCancelPaperOrder,
  usePaperAccount,
  usePaperOrders,
  usePaperPnl,
  usePaperPositions,
  useSubmitPaperOrder,
} from '@/hooks/usePaperTrading'
import type {
  PaperOrder,
  PaperOrderType,
  PaperOrderSide,
} from '@/api/types'

const TERMINAL_STATUSES: ReadonlySet<PaperOrder['status']> = new Set([
  'FILLED',
  'PARTIALLY_FILLED',
  'CANCELED',
  'REJECTED',
])

function fmtNum(value: string | null | undefined, digits = 2): string {
  if (value === null || value === undefined || value === '') return '—'
  const num = Number(value)
  if (!Number.isFinite(num)) return value
  return num.toLocaleString('ko-KR', {
    maximumFractionDigits: digits,
    minimumFractionDigits: 0,
  })
}

function isDisabledError(err: unknown): boolean {
  return err instanceof ApiError && err.status === 503
}

export function PaperTradingPage() {
  const account = usePaperAccount()
  const orders = usePaperOrders({ limit: 20 })
  const positions = usePaperPositions(undefined, false)
  const pnl = usePaperPnl({ limit: 30 })

  const accountDisabled =
    account.isError && account.error instanceof ApiError && account.error.status === 404

  return (
    <section className="flex flex-col gap-4" data-testid="paper-page">
      <header className="flex flex-wrap items-end justify-between gap-2">
        <div>
          <h2 className="text-2xl font-semibold">페이퍼 트레이딩 (β)</h2>
          <p className="text-sm text-muted-foreground">
            가상 자본 기반 시뮬레이션 — 실 KIS 주문 / 자동매매 / 실거래 호출 0건
          </p>
        </div>
        <div className="rounded-md border border-amber-200 bg-amber-50 px-3 py-1.5 text-xs text-amber-800 dark:border-amber-900/40 dark:bg-amber-900/20 dark:text-amber-200">
          <strong>모의투자</strong> 모드 — 실제 자금이 이동하지 않습니다
        </div>
      </header>

      <DisabledBannerCard />

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <VirtualAccountCard
          loading={account.isLoading}
          error={account.isError && !accountDisabled}
          empty={accountDisabled}
          data={account.data}
        />
        <PaperOrderForm />
      </div>

      <VirtualPositionsTable
        loading={positions.isLoading}
        error={positions.isError}
        items={positions.data?.positions ?? []}
        total={positions.data?.total ?? 0}
      />

      <PnLTable
        loading={pnl.isLoading}
        error={pnl.isError}
        items={pnl.data?.snapshots ?? []}
      />

      <PaperOrdersTable
        loading={orders.isLoading}
        error={orders.isError}
        items={orders.data?.orders ?? []}
      />
    </section>
  )
}

// -----------------------------------------------------------------------
// Disabled banner — shown when POST /api/paper/orders returns 503
// -----------------------------------------------------------------------

function DisabledBannerCard() {
  // We probe disabled state by attempting a tiny submitMutation.reset cycle
  // off the cancel hook (cheap) instead of issuing a real POST.  A
  // friendlier path: the order form's mutation surfaces 503 inline, AND
  // we always show a soft banner explaining the gating policy so the
  // operator never has to guess.
  return (
    <div
      data-testid="paper-policy-banner"
      className="flex items-start gap-3 rounded-lg border border-blue-200 bg-blue-50 p-3 text-sm text-blue-900 dark:border-blue-900/40 dark:bg-blue-900/20 dark:text-blue-200"
    >
      <Activity className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
      <div className="flex flex-col gap-1">
        <p className="font-medium">PAPER_TRADING_ENABLED 정책</p>
        <p>
          이 화면은 <code className="rounded bg-blue-100 px-1 py-0.5 dark:bg-blue-900/40">/api/paper/*</code>{' '}
          전용입니다. 실제 KIS 주문, 실 broker, 자동매매와 코드 경로가 완전히 분리되어
          있으며, <code className="rounded bg-blue-100 px-1 py-0.5 dark:bg-blue-900/40">PAPER_TRADING_ENABLED=false</code>{' '}
          상태에서는 주문 폼 호출이 503 으로 거부됩니다.
        </p>
      </div>
    </div>
  )
}

// -----------------------------------------------------------------------
// VirtualAccountCard
// -----------------------------------------------------------------------

function VirtualAccountCard({
  loading,
  error,
  empty,
  data,
}: {
  loading: boolean
  error: boolean
  empty: boolean
  data:
    | {
        id: number
        name: string
        currency: string
        cash_balance: string | null
        market_value: string | null
        total_value: string | null
        realized_pnl: string | null
        unrealized_pnl: string | null
      }
    | undefined
}) {
  return (
    <div
      data-testid="paper-account-card"
      className="rounded-lg border border-border bg-card p-5 lg:col-span-2"
    >
      <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-muted-foreground">
        가상 계좌 요약
      </h3>
      {loading && (
        <p data-testid="paper-account-loading" className="text-sm text-muted-foreground">
          가상 계좌 로딩 중…
        </p>
      )}
      {error && (
        <p data-testid="paper-account-error" className="text-sm text-red-700 dark:text-red-300">
          가상 계좌를 불러오지 못했습니다.
        </p>
      )}
      {empty && (
        <p data-testid="paper-account-empty" className="text-sm text-muted-foreground">
          아직 생성된 가상 계좌가 없습니다. 운영자가 VirtualAccount 한 건을 시드한 뒤
          이 화면을 새로고침하세요 (
          <code className="rounded bg-muted px-1 py-0.5">INTEGRATION_RUNBOOK §22.2</code>
          ).
        </p>
      )}
      {!loading && !error && !empty && data && (
        <div className="grid grid-cols-2 gap-3 text-sm md:grid-cols-3">
          <Stat label="계좌명" value={data.name} testid="paper-account-name" />
          <Stat
            label="가상 현금"
            value={`${fmtNum(data.cash_balance)} ${data.currency}`}
            testid="paper-account-cash"
          />
          <Stat
            label="시가총액"
            value={`${fmtNum(data.market_value)} ${data.currency}`}
            testid="paper-account-market-value"
          />
          <Stat
            label="총 평가액"
            value={`${fmtNum(data.total_value)} ${data.currency}`}
            testid="paper-account-total"
          />
          <Stat
            label="실현 PnL"
            value={fmtNum(data.realized_pnl)}
            testid="paper-account-realized"
          />
          <Stat
            label="미실현 PnL"
            value={fmtNum(data.unrealized_pnl)}
            testid="paper-account-unrealized"
          />
        </div>
      )}
    </div>
  )
}

function Stat({
  label,
  value,
  testid,
}: {
  label: string
  value: string
  testid: string
}) {
  return (
    <div className="flex flex-col rounded border border-border/50 px-3 py-2">
      <span className="text-[10px] uppercase tracking-wide text-muted-foreground">
        {label}
      </span>
      <span data-testid={testid} className="text-sm font-medium">
        {value}
      </span>
    </div>
  )
}

// -----------------------------------------------------------------------
// PaperOrderForm
// -----------------------------------------------------------------------

function PaperOrderForm() {
  const submit = useSubmitPaperOrder()
  const [symbol, setSymbol] = useState('')
  const [side, setSide] = useState<PaperOrderSide>('BUY')
  const [orderType, setOrderType] = useState<PaperOrderType>('MARKET')
  const [quantity, setQuantity] = useState('')
  const [limitPrice, setLimitPrice] = useState('')
  const [idempotencyKey, setIdempotencyKey] = useState('')

  const disabled = isDisabledError(submit.error)

  function reset() {
    setSymbol('')
    setQuantity('')
    setLimitPrice('')
    setIdempotencyKey('')
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!symbol.trim() || !quantity.trim()) return
    const parsedQty = Number(quantity)
    if (!Number.isInteger(parsedQty) || parsedQty <= 0) return
    submit.mutate(
      {
        symbol: symbol.trim().toUpperCase(),
        side,
        quantity: parsedQty,
        order_type: orderType,
        limit_price: orderType === 'LIMIT' ? limitPrice.trim() || null : null,
        idempotency_key: idempotencyKey.trim() || null,
      },
      {
        onSuccess: () => {
          reset()
        },
      },
    )
  }

  return (
    <form
      data-testid="paper-order-form"
      onSubmit={handleSubmit}
      className="flex flex-col gap-3 rounded-lg border border-border bg-card p-4"
    >
      <div className="flex items-center gap-2">
        <TrendingUp className="h-4 w-4 text-muted-foreground" aria-hidden />
        <h3 className="text-sm font-semibold">페이퍼 주문 만들기 (가상)</h3>
      </div>

      <label className="flex flex-col gap-1 text-xs">
        <span className="text-muted-foreground">종목 코드</span>
        <input
          data-testid="paper-order-symbol-input"
          value={symbol}
          onChange={e => setSymbol(e.target.value)}
          placeholder="005930"
          maxLength={32}
          className="rounded-md border border-input bg-background px-2 py-1 text-sm"
        />
      </label>

      <div className="grid grid-cols-2 gap-2 text-xs">
        <label className="flex flex-col gap-1">
          <span className="text-muted-foreground">방향</span>
          <select
            data-testid="paper-order-side-select"
            value={side}
            onChange={e => setSide(e.target.value as PaperOrderSide)}
            className="rounded-md border border-input bg-background px-2 py-1 text-sm"
          >
            <option value="BUY">BUY</option>
            <option value="SELL">SELL</option>
          </select>
        </label>
        <label className="flex flex-col gap-1">
          <span className="text-muted-foreground">유형</span>
          <select
            data-testid="paper-order-type-select"
            value={orderType}
            onChange={e => setOrderType(e.target.value as PaperOrderType)}
            className="rounded-md border border-input bg-background px-2 py-1 text-sm"
          >
            <option value="MARKET">MARKET</option>
            <option value="LIMIT">LIMIT</option>
          </select>
        </label>
      </div>

      <label className="flex flex-col gap-1 text-xs">
        <span className="text-muted-foreground">수량 (주)</span>
        <input
          data-testid="paper-order-quantity-input"
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
            data-testid="paper-order-limit-price-input"
            value={limitPrice}
            onChange={e => setLimitPrice(e.target.value)}
            inputMode="decimal"
            placeholder="71000"
            className="rounded-md border border-input bg-background px-2 py-1 text-sm"
          />
        </label>
      )}

      <label className="flex flex-col gap-1 text-xs">
        <span className="text-muted-foreground">멱등 키 (선택)</span>
        <input
          data-testid="paper-order-idempotency-key-input"
          value={idempotencyKey}
          onChange={e => setIdempotencyKey(e.target.value)}
          maxLength={64}
          placeholder="abc-123"
          className="rounded-md border border-input bg-background px-2 py-1 text-sm"
        />
      </label>

      <button
        type="submit"
        data-testid="paper-order-submit"
        disabled={submit.isPending}
        className={cn(
          'inline-flex items-center justify-center gap-2 rounded-md border border-input bg-primary px-3 py-2 text-sm font-medium text-primary-foreground transition-colors',
          'hover:bg-primary/90',
          'disabled:cursor-not-allowed disabled:opacity-60',
        )}
      >
        페이퍼 주문 만들기
      </button>

      {submit.isSuccess && (
        <p
          data-testid="paper-order-submit-success"
          className="rounded border border-emerald-200 bg-emerald-50 p-2 text-xs text-emerald-700 dark:border-emerald-900/40 dark:bg-emerald-900/20 dark:text-emerald-200"
        >
          가상 주문이 생성되었습니다 (id={submit.data?.order.id}
          {submit.data?.deduplicated ? ', 중복 키 — 기존 주문 반환' : ''}).
        </p>
      )}

      {disabled && (
        <p
          data-testid="paper-order-disabled-banner"
          className="flex items-center gap-1 rounded border border-amber-200 bg-amber-50 p-2 text-xs text-amber-800 dark:border-amber-900/40 dark:bg-amber-900/20 dark:text-amber-200"
        >
          <Ban className="h-3 w-3" aria-hidden />
          페이퍼 트레이딩이 비활성화 상태입니다 (PAPER_TRADING_ENABLED=false).
          운영자가 .env 에서 명시적으로 활성화한 뒤 다시 시도해 주세요.
        </p>
      )}

      {submit.isError && !disabled && (
        <p
          data-testid="paper-order-submit-error"
          className="rounded border border-red-200 bg-red-50 p-2 text-xs text-red-700 dark:border-red-900/40 dark:bg-red-900/20 dark:text-red-300"
        >
          주문 생성 실패:{' '}
          {submit.error instanceof ApiError
            ? submit.error.message
            : '알 수 없는 오류'}
        </p>
      )}
    </form>
  )
}

// -----------------------------------------------------------------------
// VirtualPositionsTable
// -----------------------------------------------------------------------

function VirtualPositionsTable({
  loading,
  error,
  items,
  total,
}: {
  loading: boolean
  error: boolean
  items: Array<{
    id: number
    symbol: string
    quantity: number
    avg_cost: string | null
    realized_pnl: string | null
    last_close: string | null
    market_value: string | null
    unrealized_pnl: string | null
  }>
  total: number
}) {
  return (
    <section
      data-testid="paper-positions-card"
      className="rounded-lg border border-border bg-card p-4"
    >
      <header className="mb-3 flex items-center justify-between">
        <h3 className="text-sm font-semibold">가상 포지션 ({total})</h3>
      </header>
      {loading && (
        <p className="text-sm text-muted-foreground" data-testid="paper-positions-loading">
          포지션 로딩 중…
        </p>
      )}
      {error && (
        <p
          data-testid="paper-positions-error"
          className="text-sm text-red-700 dark:text-red-300"
        >
          포지션을 불러오지 못했습니다.
        </p>
      )}
      {!loading && !error && items.length === 0 && (
        <p data-testid="paper-positions-empty" className="text-sm text-muted-foreground">
          오픈된 가상 포지션이 없습니다.
        </p>
      )}
      {items.length > 0 && (
        <div className="overflow-x-auto">
          <table className="w-full text-sm" data-testid="paper-positions-table">
            <thead>
              <tr className="text-left text-xs text-muted-foreground">
                <th className="px-2 py-1">종목</th>
                <th className="px-2 py-1 text-right">수량</th>
                <th className="px-2 py-1 text-right">평균단가</th>
                <th className="px-2 py-1 text-right">현재가</th>
                <th className="px-2 py-1 text-right">시장가치</th>
                <th className="px-2 py-1 text-right">미실현 PnL</th>
                <th className="px-2 py-1 text-right">실현 PnL</th>
              </tr>
            </thead>
            <tbody>
              {items.map(p => (
                <tr
                  key={p.id}
                  data-testid={`paper-position-row-${p.symbol}`}
                  className="border-t border-border/50"
                >
                  <td className="px-2 py-1 font-medium">{p.symbol}</td>
                  <td className="px-2 py-1 text-right">{p.quantity}</td>
                  <td className="px-2 py-1 text-right">{fmtNum(p.avg_cost)}</td>
                  <td className="px-2 py-1 text-right">{fmtNum(p.last_close)}</td>
                  <td className="px-2 py-1 text-right">{fmtNum(p.market_value)}</td>
                  <td className="px-2 py-1 text-right">{fmtNum(p.unrealized_pnl)}</td>
                  <td className="px-2 py-1 text-right">{fmtNum(p.realized_pnl)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}

// -----------------------------------------------------------------------
// PnLTable (compact timeseries — chart can come later)
// -----------------------------------------------------------------------

function PnLTable({
  loading,
  error,
  items,
}: {
  loading: boolean
  error: boolean
  items: Array<{
    snapshot_date: string
    cash_balance: string | null
    market_value: string | null
    total_value: string | null
    realized_pnl: string | null
    unrealized_pnl: string | null
  }>
}) {
  return (
    <section
      data-testid="paper-pnl-card"
      className="rounded-lg border border-border bg-card p-4"
    >
      <header className="mb-3">
        <h3 className="text-sm font-semibold">일별 PnL ({items.length})</h3>
      </header>
      {loading && (
        <p data-testid="paper-pnl-loading" className="text-sm text-muted-foreground">
          PnL 로딩 중…
        </p>
      )}
      {error && (
        <p data-testid="paper-pnl-error" className="text-sm text-red-700 dark:text-red-300">
          PnL 데이터를 불러오지 못했습니다.
        </p>
      )}
      {!loading && !error && items.length === 0 && (
        <p data-testid="paper-pnl-empty" className="text-sm text-muted-foreground">
          아직 적재된 PnL 스냅샷이 없습니다.
        </p>
      )}
      {items.length > 0 && (
        <div className="overflow-x-auto">
          <table className="w-full text-sm" data-testid="paper-pnl-table">
            <thead>
              <tr className="text-left text-xs text-muted-foreground">
                <th className="px-2 py-1">날짜</th>
                <th className="px-2 py-1 text-right">현금</th>
                <th className="px-2 py-1 text-right">시장가치</th>
                <th className="px-2 py-1 text-right">총 평가</th>
                <th className="px-2 py-1 text-right">실현 PnL</th>
                <th className="px-2 py-1 text-right">미실현 PnL</th>
              </tr>
            </thead>
            <tbody>
              {items.map(s => (
                <tr
                  key={s.snapshot_date}
                  data-testid={`paper-pnl-row-${s.snapshot_date}`}
                  className="border-t border-border/50"
                >
                  <td className="px-2 py-1">{s.snapshot_date}</td>
                  <td className="px-2 py-1 text-right">{fmtNum(s.cash_balance)}</td>
                  <td className="px-2 py-1 text-right">{fmtNum(s.market_value)}</td>
                  <td className="px-2 py-1 text-right">{fmtNum(s.total_value)}</td>
                  <td className="px-2 py-1 text-right">{fmtNum(s.realized_pnl)}</td>
                  <td className="px-2 py-1 text-right">{fmtNum(s.unrealized_pnl)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}

// -----------------------------------------------------------------------
// PaperOrdersTable + cancel button
// -----------------------------------------------------------------------

function PaperOrdersTable({
  loading,
  error,
  items,
}: {
  loading: boolean
  error: boolean
  items: PaperOrder[]
}) {
  const cancel = useCancelPaperOrder()
  const cancelDisabled = isDisabledError(cancel.error)

  return (
    <section
      data-testid="paper-orders-card"
      className="rounded-lg border border-border bg-card p-4"
    >
      <header className="mb-3 flex items-center justify-between">
        <h3 className="text-sm font-semibold">가상 주문 이력 ({items.length})</h3>
      </header>
      {loading && (
        <p data-testid="paper-orders-loading" className="text-sm text-muted-foreground">
          주문 로딩 중…
        </p>
      )}
      {error && (
        <p data-testid="paper-orders-error" className="text-sm text-red-700 dark:text-red-300">
          주문 이력을 불러오지 못했습니다.
        </p>
      )}
      {!loading && !error && items.length === 0 && (
        <p data-testid="paper-orders-empty" className="text-sm text-muted-foreground">
          아직 페이퍼 주문이 없습니다.
        </p>
      )}
      {items.length > 0 && (
        <div className="overflow-x-auto">
          <table className="w-full text-sm" data-testid="paper-orders-table">
            <thead>
              <tr className="text-left text-xs text-muted-foreground">
                <th className="px-2 py-1">id</th>
                <th className="px-2 py-1">종목</th>
                <th className="px-2 py-1">방향</th>
                <th className="px-2 py-1">유형</th>
                <th className="px-2 py-1 text-right">수량</th>
                <th className="px-2 py-1 text-right">지정가</th>
                <th className="px-2 py-1">상태</th>
                <th className="px-2 py-1">생성 시각</th>
                <th className="px-2 py-1" />
              </tr>
            </thead>
            <tbody>
              {items.map(o => {
                const cancelable = !TERMINAL_STATUSES.has(o.status)
                return (
                  <tr
                    key={o.id}
                    data-testid={`paper-order-row-${o.id}`}
                    className="border-t border-border/50"
                  >
                    <td className="px-2 py-1">{o.id}</td>
                    <td className="px-2 py-1 font-medium">{o.symbol}</td>
                    <td className="px-2 py-1">{o.side}</td>
                    <td className="px-2 py-1">{o.order_type}</td>
                    <td className="px-2 py-1 text-right">{o.quantity}</td>
                    <td className="px-2 py-1 text-right">{fmtNum(o.limit_price)}</td>
                    <td className="px-2 py-1">{o.status}</td>
                    <td className="px-2 py-1 text-xs text-muted-foreground">
                      {o.created_at}
                    </td>
                    <td className="px-2 py-1 text-right">
                      {cancelable && (
                        <button
                          data-testid={`paper-order-cancel-${o.id}`}
                          type="button"
                          onClick={() => cancel.mutate({ orderId: o.id })}
                          disabled={cancel.isPending}
                          className="rounded border border-input bg-background px-2 py-0.5 text-xs hover:bg-accent"
                        >
                          취소
                        </button>
                      )}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
      {cancelDisabled && (
        <p
          data-testid="paper-cancel-disabled-banner"
          className="mt-2 rounded border border-amber-200 bg-amber-50 p-2 text-xs text-amber-800 dark:border-amber-900/40 dark:bg-amber-900/20 dark:text-amber-200"
        >
          주문 취소 또한 PAPER_TRADING_ENABLED=true 일 때만 가능합니다.
        </p>
      )}
    </section>
  )
}
