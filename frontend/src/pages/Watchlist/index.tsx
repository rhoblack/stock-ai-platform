// v0.8 Phase D — Watchlist management page (/watchlist).
// Shows user's watchlists, allows creating new lists, adding / removing
// symbols. Mutations map to Phase C backend APIs.
//
// Policy:
//   • No order / buy / sell / auto-trading UI — watchlist is a bookmarks
//     list only.
//   • Forbidden fields (broker, account, quantity, order_*, source_file_path,
//     password, token) are never rendered.
//   • 401 / 404 / 409 / 422 errors are surfaced with plain text messages.

import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Star, Trash2, Plus, List } from 'lucide-react'
import {
  useWatchlists,
  useWatchlist,
  useCreateWatchlist,
  useAddWatchlistItem,
  useRemoveWatchlistItem,
} from '@/hooks/useWatchlists'
import { ApiError } from '@/api/client'
import { cn } from '@/lib/utils'
import type { Watchlist } from '@/api/types'

export function WatchlistPage() {
  const { data, isLoading, isError } = useWatchlists()
  const [selectedId, setSelectedId] = useState<number | null>(null)

  // After watchlists load, default-select the first one if nothing is selected
  const watchlists = data?.watchlists ?? []
  const activeId =
    selectedId !== null
      ? selectedId
      : (watchlists.find(w => w.is_default) ?? watchlists[0])?.id ?? null

  if (isLoading) {
    return (
      <section data-testid="watchlist-page" className="flex flex-col gap-4">
        <h2 className="text-2xl font-semibold">관심종목</h2>
        <p className="text-sm text-muted-foreground">관심목록 로딩 중…</p>
      </section>
    )
  }

  if (isError) {
    return (
      <section data-testid="watchlist-page" className="flex flex-col gap-4">
        <h2 className="text-2xl font-semibold">관심종목</h2>
        <div
          data-testid="watchlist-error"
          className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700 dark:border-red-900/40 dark:bg-red-900/20 dark:text-red-300"
        >
          관심목록을 불러오지 못했습니다.
        </div>
      </section>
    )
  }

  return (
    <section data-testid="watchlist-page" className="flex flex-col gap-6">
      <header className="flex flex-wrap items-end justify-between gap-2">
        <div>
          <h2 className="text-2xl font-semibold">관심종목</h2>
          <p className="text-sm text-muted-foreground">종목 즐겨찾기 관리</p>
        </div>
      </header>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        {/* Left: watchlist list + create form */}
        <aside className="flex flex-col gap-3">
          <WatchlistListPanel
            watchlists={watchlists}
            activeId={activeId}
            onSelect={id => setSelectedId(id)}
          />
          <CreateWatchlistPanel />
        </aside>

        {/* Right: selected watchlist detail */}
        <div className="lg:col-span-2">
          {activeId !== null ? (
            <WatchlistDetailPanel watchlistId={activeId} />
          ) : (
            <div
              data-testid="watchlist-detail-empty"
              className="flex flex-col items-center justify-center rounded-lg border border-dashed border-border bg-card p-12 text-center"
            >
              <Star className="mb-3 h-8 w-8 text-muted-foreground" />
              <p className="text-sm text-muted-foreground">
                왼쪽에서 관심목록을 선택하거나 새 목록을 만들어 주세요.
              </p>
            </div>
          )}
        </div>
      </div>
    </section>
  )
}

// ---------------------------------------------------------------------------
// Watchlist list panel
// ---------------------------------------------------------------------------

function WatchlistListPanel({
  watchlists,
  activeId,
  onSelect,
}: {
  watchlists: Watchlist[]
  activeId: number | null
  onSelect: (id: number) => void
}) {
  return (
    <section
      data-testid="watchlist-list"
      className="rounded-lg border border-border bg-card p-4"
    >
      <header className="mb-3 flex items-center gap-2">
        <List className="h-4 w-4 text-muted-foreground" />
        <h3 className="text-sm font-semibold">내 목록 ({watchlists.length})</h3>
      </header>

      {watchlists.length === 0 ? (
        <p
          data-testid="watchlist-list-empty"
          className="text-sm text-muted-foreground"
        >
          관심목록이 없습니다.
        </p>
      ) : (
        <ul className="flex flex-col gap-1">
          {watchlists.map(wl => (
            <li key={wl.id}>
              <button
                type="button"
                data-testid={`watchlist-row-${wl.id}`}
                onClick={() => onSelect(wl.id)}
                className={cn(
                  'flex w-full items-center gap-2 rounded-md px-3 py-2 text-sm transition-colors hover:bg-accent',
                  activeId === wl.id && 'bg-accent font-medium',
                )}
              >
                <Star
                  className={cn(
                    'h-3 w-3 shrink-0',
                    wl.is_default
                      ? 'fill-yellow-400 text-yellow-400'
                      : 'text-muted-foreground',
                  )}
                />
                <span className="flex-1 truncate text-left">{wl.name}</span>
                <span className="shrink-0 font-mono text-xs text-muted-foreground">
                  {wl.item_count}
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}

// ---------------------------------------------------------------------------
// Create watchlist panel
// ---------------------------------------------------------------------------

function CreateWatchlistPanel() {
  const createMutation = useCreateWatchlist()
  const [name, setName] = useState('')
  const [errorMsg, setErrorMsg] = useState<string | null>(null)

  async function handleCreate(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault()
    const trimmed = name.trim()
    if (!trimmed || createMutation.isPending) return
    setErrorMsg(null)
    try {
      await createMutation.mutateAsync({ name: trimmed })
      setName('')
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.status === 409) {
          setErrorMsg('같은 이름의 관심목록이 이미 있습니다.')
        } else if (err.status === 422) {
          setErrorMsg('목록 이름이 올바르지 않습니다 (최대 64자).')
        } else {
          setErrorMsg('관심목록 생성에 실패했습니다.')
        }
      } else {
        setErrorMsg('관심목록 생성에 실패했습니다.')
      }
    }
  }

  return (
    <section
      data-testid="watchlist-create-form"
      className="rounded-lg border border-border bg-card p-4"
    >
      <h3 className="mb-3 text-sm font-semibold">새 관심목록 만들기</h3>
      <form onSubmit={handleCreate} noValidate>
        <input
          data-testid="watchlist-create-name"
          type="text"
          placeholder="목록 이름 (최대 64자)"
          value={name}
          onChange={e => setName(e.target.value)}
          disabled={createMutation.isPending}
          maxLength={64}
          className="mb-2 w-full rounded-md border border-border bg-background px-3 py-1.5 text-sm outline-none focus:ring-2 focus:ring-primary disabled:opacity-50"
        />
        {errorMsg && (
          <p
            data-testid="watchlist-create-error"
            role="alert"
            className="mb-2 text-xs text-red-600 dark:text-red-300"
          >
            {errorMsg}
          </p>
        )}
        <button
          type="submit"
          data-testid="watchlist-create-submit"
          disabled={createMutation.isPending || !name.trim()}
          className="flex w-full items-center justify-center gap-1.5 rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90 disabled:opacity-50"
        >
          <Plus className="h-3.5 w-3.5" />
          {createMutation.isPending ? '생성 중…' : '만들기'}
        </button>
      </form>
    </section>
  )
}

// ---------------------------------------------------------------------------
// Watchlist detail panel
// ---------------------------------------------------------------------------

function WatchlistDetailPanel({ watchlistId }: { watchlistId: number }) {
  const { data, isLoading, isError } = useWatchlist(watchlistId)

  if (isLoading) {
    return (
      <div
        data-testid="watchlist-detail-loading"
        className="rounded-lg border border-border bg-card p-6 text-sm text-muted-foreground"
      >
        관심목록 로딩 중…
      </div>
    )
  }

  if (isError || !data) {
    return (
      <div
        data-testid="watchlist-detail-error"
        className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700 dark:border-red-900/40 dark:bg-red-900/20 dark:text-red-300"
      >
        관심목록을 불러오지 못했습니다.
      </div>
    )
  }

  return (
    <section
      data-testid="watchlist-detail"
      className="flex flex-col gap-4 rounded-lg border border-border bg-card p-5"
    >
      <header className="flex items-center gap-2">
        <Star
          className={cn(
            'h-4 w-4',
            data.is_default ? 'fill-yellow-400 text-yellow-400' : 'text-muted-foreground',
          )}
        />
        <h3 className="text-sm font-semibold">{data.name}</h3>
        {data.is_default && (
          <span className="rounded-full bg-yellow-100 px-2 py-0.5 text-xs text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-300">
            기본
          </span>
        )}
        <span className="ml-auto text-xs text-muted-foreground">
          {data.item_count}종목
        </span>
      </header>

      {/* Item list */}
      {data.items.length === 0 ? (
        <p
          data-testid="watchlist-items-empty"
          className="text-sm text-muted-foreground"
        >
          종목이 없습니다. 아래에서 종목을 추가해 주세요.
        </p>
      ) : (
        <ul className="flex flex-col divide-y divide-border">
          {data.items.map(item => (
            <WatchlistItemRow
              key={item.symbol}
              watchlistId={watchlistId}
              symbol={item.symbol}
              memo={item.memo}
            />
          ))}
        </ul>
      )}

      {/* Add item form */}
      <AddItemForm watchlistId={watchlistId} />
    </section>
  )
}

// ---------------------------------------------------------------------------
// Watchlist item row
// ---------------------------------------------------------------------------

function WatchlistItemRow({
  watchlistId,
  symbol,
  memo,
}: {
  watchlistId: number
  symbol: string
  memo: string | null
}) {
  const removeMutation = useRemoveWatchlistItem()
  const [removeError, setRemoveError] = useState<string | null>(null)

  async function handleRemove() {
    setRemoveError(null)
    try {
      await removeMutation.mutateAsync({ watchlistId, symbol })
    } catch {
      setRemoveError('삭제에 실패했습니다.')
    }
  }

  return (
    <li
      data-testid={`watchlist-item-${symbol}`}
      className="flex items-center gap-3 py-2.5"
    >
      <Link
        to={`/stocks/${symbol}`}
        className="flex-1 text-sm font-medium hover:underline"
        data-testid={`watchlist-item-link-${symbol}`}
      >
        {symbol}
      </Link>
      {memo && (
        <span
          data-testid={`watchlist-item-memo-${symbol}`}
          className="max-w-[200px] truncate text-xs text-muted-foreground"
          title={memo}
        >
          {memo}
        </span>
      )}
      {removeError && (
        <span className="text-xs text-red-600 dark:text-red-300">{removeError}</span>
      )}
      <button
        type="button"
        data-testid={`watchlist-item-remove-${symbol}`}
        aria-label={`${symbol} 관심목록에서 제거`}
        disabled={removeMutation.isPending}
        onClick={handleRemove}
        className="rounded-md p-1 text-muted-foreground transition-colors hover:bg-red-50 hover:text-red-600 disabled:opacity-50 dark:hover:bg-red-900/20 dark:hover:text-red-300"
      >
        <Trash2 className="h-3.5 w-3.5" />
      </button>
    </li>
  )
}

// ---------------------------------------------------------------------------
// Add item form
// ---------------------------------------------------------------------------

function AddItemForm({ watchlistId }: { watchlistId: number }) {
  const addMutation = useAddWatchlistItem()
  const [symbol, setSymbol] = useState('')
  const [memo, setMemo] = useState('')
  const [errorMsg, setErrorMsg] = useState<string | null>(null)

  async function handleAdd(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault()
    const sym = symbol.trim().toUpperCase()
    if (!sym || addMutation.isPending) return
    setErrorMsg(null)
    try {
      await addMutation.mutateAsync({
        watchlistId,
        symbol: sym,
        memo: memo.trim() || undefined,
      })
      setSymbol('')
      setMemo('')
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.status === 404) {
          setErrorMsg('존재하지 않는 종목 코드입니다.')
        } else if (err.status === 409) {
          setErrorMsg('이미 관심목록에 있는 종목입니다.')
        } else if (err.status === 422) {
          setErrorMsg('입력값이 올바르지 않습니다 (메모 최대 500자).')
        } else if (err.status === 401) {
          setErrorMsg('로그인이 필요합니다.')
        } else {
          setErrorMsg('종목 추가에 실패했습니다.')
        }
      } else {
        setErrorMsg('종목 추가에 실패했습니다.')
      }
    }
  }

  return (
    <section
      data-testid="watchlist-add-item-form"
      className="rounded-md border border-dashed border-border bg-background/50 p-4"
    >
      <h4 className="mb-3 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
        종목 추가
      </h4>
      <form onSubmit={handleAdd} noValidate className="flex flex-col gap-2">
        <div className="flex gap-2">
          <input
            data-testid="watchlist-add-symbol"
            type="text"
            placeholder="종목 코드 (예: 005930)"
            value={symbol}
            onChange={e => setSymbol(e.target.value)}
            disabled={addMutation.isPending}
            maxLength={32}
            className="flex-1 rounded-md border border-border bg-background px-3 py-1.5 text-sm outline-none focus:ring-2 focus:ring-primary disabled:opacity-50"
          />
          <button
            type="submit"
            data-testid="watchlist-add-submit"
            disabled={addMutation.isPending || !symbol.trim()}
            className="rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90 disabled:opacity-50"
          >
            {addMutation.isPending ? '추가 중…' : '추가'}
          </button>
        </div>
        <input
          data-testid="watchlist-add-memo"
          type="text"
          placeholder="메모 (선택, 최대 500자)"
          value={memo}
          onChange={e => setMemo(e.target.value)}
          disabled={addMutation.isPending}
          maxLength={500}
          className="rounded-md border border-border bg-background px-3 py-1.5 text-sm outline-none focus:ring-2 focus:ring-primary disabled:opacity-50"
        />
        {errorMsg && (
          <p
            data-testid="watchlist-add-error"
            role="alert"
            className="text-xs text-red-600 dark:text-red-300"
          >
            {errorMsg}
          </p>
        )}
      </form>
    </section>
  )
}
