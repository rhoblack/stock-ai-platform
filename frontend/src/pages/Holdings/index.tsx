import { PagePlaceholder } from '@/components/PagePlaceholder'

export function HoldingsPage() {
  return (
    <PagePlaceholder
      title="보유 종목 점검"
      description="보유 종목 list + PRE/POST 최신 점검 + 종목별 추세 metric (alert / high_risk / score change)."
      apis={[
        'GET /api/holdings',
        'GET /api/holdings/checks/latest',
        'GET /api/holdings/{symbol}/checks',
      ]}
    />
  )
}
