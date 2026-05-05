import { useParams } from 'react-router-dom'
import { PagePlaceholder } from '@/components/PagePlaceholder'

export function StockDetailPage() {
  const { symbol } = useParams<{ symbol: string }>()
  return (
    <PagePlaceholder
      title={symbol ? `종목 상세 — ${symbol}` : '종목 상세'}
      description="종목 기본정보 + 최신 일봉 / 지표 + 최근 추천 이력 (1/3/5/20일 성과 join) + 보유 점검 이력."
      apis={['GET /api/stocks/{symbol}']}
    />
  )
}
