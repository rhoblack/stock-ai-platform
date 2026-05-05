import { useQuery } from '@tanstack/react-query'
import { apiFetch } from '@/api/client'
import type { HealthResponse } from '@/api/types'

export function useHealth() {
  return useQuery({
    queryKey: ['health'],
    queryFn: () => apiFetch<HealthResponse>('/health'),
    refetchInterval: 30_000,
    staleTime: 10_000,
  })
}
