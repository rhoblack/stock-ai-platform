import { PagePlaceholder } from '@/components/PagePlaceholder'

export function MarketCapTopPage() {
  return (
    <PagePlaceholder
      title="시가총액 TOP"
      description="당일자 시총 상위 (KOSPI / KOSDAQ) + 정렬 / 검색 / 분석 대상 표시."
      apis={['GET /api/universe/market-cap-top']}
    />
  )
}
