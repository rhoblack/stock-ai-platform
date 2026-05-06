// Watchlist API client.
// v0.8 Phase D: GET list/detail, POST create/add item, DELETE item
// v0.9 Phase D: PATCH watchlist (rename/setDefault), DELETE watchlist,
//               GET items (paginated), PATCH item memo

import { apiFetch, apiDelete, apiPatch, apiPost } from './client'
import type {
  Watchlist,
  WatchlistDetail,
  WatchlistItem,
  WatchlistItemsResponse,
  WatchlistStatusResponse,
  WatchlistsResponse,
} from './types'

export function listWatchlists(): Promise<WatchlistsResponse> {
  return apiFetch<WatchlistsResponse>('/api/watchlists')
}

export function getWatchlist(id: number): Promise<WatchlistDetail> {
  return apiFetch<WatchlistDetail>(`/api/watchlists/${id}`)
}

export function createWatchlist(name: string, isDefault = false): Promise<Watchlist> {
  return apiPost<Watchlist, { name: string; is_default: boolean }>(
    '/api/watchlists',
    { name, is_default: isDefault },
  )
}

export function addWatchlistItem(
  watchlistId: number,
  symbol: string,
  memo?: string,
): Promise<WatchlistItem> {
  return apiPost<WatchlistItem, { symbol: string; memo?: string }>(
    `/api/watchlists/${watchlistId}/items`,
    memo !== undefined ? { symbol, memo } : { symbol },
  )
}

export function removeWatchlistItem(
  watchlistId: number,
  symbol: string,
): Promise<WatchlistStatusResponse> {
  return apiDelete<WatchlistStatusResponse>(
    `/api/watchlists/${watchlistId}/items/${symbol}`,
  )
}

// ---------------------------------------------------------------------------
// v0.9 Phase C/D additions
// ---------------------------------------------------------------------------

export interface WatchlistUpdatePayload {
  name?: string
  is_default?: boolean
}

export function updateWatchlist(
  watchlistId: number,
  payload: WatchlistUpdatePayload,
): Promise<Watchlist> {
  return apiPatch<Watchlist, WatchlistUpdatePayload>(
    `/api/watchlists/${watchlistId}`,
    payload,
  )
}

export function deleteWatchlist(watchlistId: number): Promise<WatchlistStatusResponse> {
  return apiDelete<WatchlistStatusResponse>(`/api/watchlists/${watchlistId}`)
}

export function updateWatchlistItemMemo(
  watchlistId: number,
  symbol: string,
  memo: string | null,
): Promise<WatchlistItem> {
  return apiPatch<WatchlistItem, { memo: string | null }>(
    `/api/watchlists/${watchlistId}/items/${symbol}`,
    { memo },
  )
}

export function listWatchlistItems(
  watchlistId: number,
  params?: {
    limit?: number
    offset?: number
    symbol_prefix?: string
  },
): Promise<WatchlistItemsResponse> {
  return apiFetch<WatchlistItemsResponse>(`/api/watchlists/${watchlistId}/items`, {
    searchParams: params,
  })
}
