// v0.8 Phase D — Watchlist React Query hooks.
// Queries: useWatchlists, useWatchlist
// Mutations: useCreateWatchlist, useAddWatchlistItem, useRemoveWatchlistItem
// Derived: useDefaultWatchlistId, useIsInWatchlist

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  addWatchlistItem,
  createWatchlist,
  getWatchlist,
  listWatchlists,
  removeWatchlistItem,
} from '@/api/watchlists'

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
