import { useQuery } from '@tanstack/react-query'
import { apiFetch } from '@/api/client'
import type { TodayReportResponse } from '@/api/types'

export function useTodayReport() {
  return useQuery({
    queryKey: ['reports', 'today'],
    queryFn: () => apiFetch<TodayReportResponse>('/api/reports/today'),
    refetchInterval: 60_000,
    staleTime: 20_000,
  })
}
