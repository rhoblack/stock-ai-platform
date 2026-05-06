// Watchlist React Query hooks.
// v0.8 Phase D: useWatchlists, useWatchlist, useCreateWatchlist,
//               useAddWatchlistItem, useRemoveWatchlistItem,
//               useDefaultWatchlistId, useIsInWatchlist
// v0.9 Phase D: useUpdateWatchlist, useDeleteWatchlist,
//               useUpdateWatchlistItemMemo

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  addWatchlistItem,
  createWatchlist,
  deleteWatchlist,
  getWatchlist,
  listWatchlists,
  removeWatchlistItem,
  updateWatchlist,
  updateWatchlistItemMemo,
} from '@/api/watchlists'
import type { WatchlistUpdatePayload } from '@/api/watchlists'

// ---------------------------------------------------------------------------
// Query: list of watchlists
// ---------------------------------------------------------------------------

export function useWatchlists() {
  return useQuery({
    queryKey: ['watchlists'],
    queryFn: listWatchlists,
    staleTime: 30_000,
  })
}

// ---------------------------------------------------------------------------
// Query: single watchlist detail (items)
// ---------------------------------------------------------------------------

export function useWatchlist(id: number | null | undefined) {
  return useQuery({
    queryKey: ['watchlists', id],
    enabled: id != null && id > 0,
    queryFn: () => getWatchlist(id!),
    staleTime: 30_000,
  })
}

// ---------------------------------------------------------------------------
// Derived: ID of the default (or first) watchlist
// ---------------------------------------------------------------------------

export function useDefaultWatchlistId(): number | null {
  const { data } = useWatchlists()
  if (!data?.watchlists.length) return null
  return (data.watchlists.find(w => w.is_default) ?? data.watchlists[0]).id
}

// ---------------------------------------------------------------------------
// Derived: is a symbol present in the default watchlist?
// ---------------------------------------------------------------------------

export function useIsInWatchlist(symbol: string): boolean {
  const defaultId = useDefaultWatchlistId()
  const { data } = useWatchlist(defaultId)
  return data?.items.some(i => i.symbol === symbol) ?? false
}

// ---------------------------------------------------------------------------
// Mutation: create watchlist
// ---------------------------------------------------------------------------

export function useCreateWatchlist() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ name, isDefault }: { name: string; isDefault?: boolean }) =>
      createWatchlist(name, isDefault),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['watchlists'] })
    },
  })
}

// ---------------------------------------------------------------------------
// Mutation: add item to a watchlist
// ---------------------------------------------------------------------------

export function useAddWatchlistItem() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({
      watchlistId,
      symbol,
      memo,
    }: {
      watchlistId: number
      symbol: string
      memo?: string
    }) => addWatchlistItem(watchlistId, symbol, memo),
    onSuccess: (_data, { watchlistId }) => {
      void queryClient.invalidateQueries({ queryKey: ['watchlists', watchlistId] })
      void queryClient.invalidateQueries({ queryKey: ['watchlists'] })
    },
  })
}

// ---------------------------------------------------------------------------
// Mutation: remove item from a watchlist
// ---------------------------------------------------------------------------

export function useRemoveWatchlistItem() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ watchlistId, symbol }: { watchlistId: number; symbol: string }) =>
      removeWatchlistItem(watchlistId, symbol),
    onSuccess: (_data, { watchlistId }) => {
      void queryClient.invalidateQueries({ queryKey: ['watchlists', watchlistId] })
      void queryClient.invalidateQueries({ queryKey: ['watchlists'] })
    },
  })
}

// ---------------------------------------------------------------------------
// Mutation: update watchlist (rename / set default) — v0.9 Phase D
// ---------------------------------------------------------------------------

export function useUpdateWatchlist() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({
      watchlistId,
      payload,
    }: {
      watchlistId: number
      payload: WatchlistUpdatePayload
    }) => updateWatchlist(watchlistId, payload),
    onSuccess: (_data, { watchlistId }) => {
      void queryClient.invalidateQueries({ queryKey: ['watchlists', watchlistId] })
      void queryClient.invalidateQueries({ queryKey: ['watchlists'] })
    },
  })
}

// ---------------------------------------------------------------------------
// Mutation: delete watchlist — v0.9 Phase D
// ---------------------------------------------------------------------------

export function useDeleteWatchlist() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (watchlistId: number) => deleteWatchlist(watchlistId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['watchlists'] })
      // Also invalidate user preferences since default_watchlist_id may be cleared
      void queryClient.invalidateQueries({ queryKey: ['userPreferences'] })
    },
  })
}

// ---------------------------------------------------------------------------
// Mutation: update watchlist item memo — v0.9 Phase D
// ---------------------------------------------------------------------------

export function useUpdateWatchlistItemMemo() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({
      watchlistId,
      symbol,
      memo,
    }: {
      watchlistId: number
      symbol: string
      memo: string | null
    }) => updateWatchlistItemMemo(watchlistId, symbol, memo),
    onSuccess: (_data, { watchlistId }) => {
      void queryClient.invalidateQueries({ queryKey: ['watchlists', watchlistId] })
    },
  })
}
