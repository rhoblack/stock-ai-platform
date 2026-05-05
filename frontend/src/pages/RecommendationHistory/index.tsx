import { PagePlaceholder } from '@/components/PagePlaceholder'

export function RecommendationHistoryPage() {
  return (
    <PagePlaceholder
      title="추천 이력"
      description="최근 run 별 success_rate / avg_close_return_{1,3,5,20}d 집계 + 시계열."
      apis={['GET /api/recommendations/history']}
    />
  )
}
