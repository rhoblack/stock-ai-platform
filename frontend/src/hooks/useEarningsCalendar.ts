import { useQuery } from '@tanstack/react-query'
import { apiFetch } from '@/api/client'
import type { EarningsCalendarResponse } from '@/api/types'

export interface UseEarningsCalendarParams {
  fromDate?: string
  toDate?: string
  surpriseType?: string
  limit?: number
}

export function useEarningsCalendar(
  params: UseEarningsCalendarParams = {},
) {
  const { fromDate, toDate, surpriseType, limit = 20 } = params
  return useQuery({
    queryKey: [
      'calendar',
      'earnings',
      { fromDate, toDate, surpriseType, limit },
    ],
    queryFn: () =>
      apiFetch<EarningsCalendarResponse>('/api/calendar/earnings', {
        searchParams: {
          from_date: fromDate,
          to_date: toDate,
          surprise_type: surpriseType,
          limit,
        },
      }),
    staleTime: 60_000,
  })
}
