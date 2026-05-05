import { PagePlaceholder } from '@/components/PagePlaceholder'

export function TodayReportPage() {
  return (
    <PagePlaceholder
      title="오늘의 리포트"
      description="추천 TOP / 보유 점검 PRE+POST / 위험 ALERT / 마지막 잡 status 종합 화면."
      apis={['GET /api/reports/today']}
    />
  )
}
