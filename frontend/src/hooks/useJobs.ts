import { useQuery } from '@tanstack/react-query'
import { apiFetch } from '@/api/client'
import type { JobsResponse } from '@/api/types'

export interface UseJobsOptions {
  jobName?: string
  status?: string
  startDate?: string
  endDate?: string
  limit?: number
  offset?: number
}

export function useJobs(options: UseJobsOptions = {}) {
  const { jobName, status, startDate, endDate, limit = 50, offset = 0 } = options
  return useQuery({
    queryKey: ['jobs', { jobName, status, startDate, endDate, limit, offset }],
    queryFn: () =>
      apiFetch<JobsResponse>('/api/jobs', {
        searchParams: {
          job_name: jobName,
          status,
          start_date: startDate,
          end_date: endDate,
          limit,
          offset,
        },
      }),
    refetchInterval: 30_000,
    staleTime: 10_000,
  })
}
