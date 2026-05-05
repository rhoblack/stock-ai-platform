import { useQuery } from '@tanstack/react-query'
import { apiFetch } from '@/api/client'
import type { JobRunDetail } from '@/api/types'

export function useJobDetail(jobId: number | null | undefined) {
  return useQuery({
    queryKey: ['jobs', 'detail', jobId],
    enabled: jobId !== null && jobId !== undefined && Number.isFinite(jobId),
    queryFn: () => apiFetch<JobRunDetail>(`/api/jobs/${jobId}`),
    staleTime: 10_000,
  })
}
