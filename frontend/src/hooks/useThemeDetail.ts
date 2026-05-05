import { useQuery } from '@tanstack/react-query'
import { apiFetch } from '@/api/client'
import type { ThemeDetailResponse } from '@/api/types'

export interface UseThemeDetailOptions {
  mappingLimit?: number
  signalLimit?: number
}

export function useThemeDetail(
  themeId: number | null | undefined,
  options: UseThemeDetailOptions = {},
) {
  const { mappingLimit = 50, signalLimit = 50 } = options
  return useQuery({
    queryKey: ['themes', themeId, { mappingLimit, signalLimit }],
    enabled: !!themeId && Number.isFinite(themeId),
    queryFn: () =>
      apiFetch<ThemeDetailResponse>(`/api/themes/${themeId}`, {
        searchParams: {
          mapping_limit: mappingLimit,
          signal_limit: signalLimit,
        },
      }),
    staleTime: 5 * 60_000,
  })
}
