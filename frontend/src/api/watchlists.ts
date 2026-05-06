// v0.8 Phase D — Watchlist API client.
// Wraps the 5 watchlist endpoints introduced in Phase C:
//   GET    /api/watchlists
//   GET    /api/watchlists/:id
//   POST   /api/watchlists
//   POST   /api/watchlists/:id/items
//   DELETE /api/watchlists/:id/items/:symbol

import { apiFetch, apiDelete, apiPost } from './client'
import type {
  Watchlist,
  WatchlistDetail,
  WatchlistItem,
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
