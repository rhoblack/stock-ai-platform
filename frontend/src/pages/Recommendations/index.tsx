import { PagePlaceholder } from '@/components/PagePlaceholder'

export function RecommendationsPage() {
  return (
    <PagePlaceholder
      title="추천 종목"
      description="최신 run 의 TOP-N 추천 + 컴포넌트 점수 + 리스크 + 1/3/5/20일 후 성과."
      apis={[
        'GET /api/recommendations/latest',
        'GET /api/recommendations/runs/{run_id}',
      ]}
    />
  )
}
