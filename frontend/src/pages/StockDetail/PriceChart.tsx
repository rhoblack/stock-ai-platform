import { useMemo } from 'react'
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import type { DailyPriceRow } from '@/api/types'
import { cn } from '@/lib/utils'

interface PriceChartProps {
  prices: DailyPriceRow[]
  height?: number
  className?: string
}

interface ChartPoint {
  date: string
  close: number | null
  volume: number
}

function buildPoints(prices: DailyPriceRow[]): ChartPoint[] {
  return prices.map(p => ({
    date: p.date,
    close: p.close === null ? null : Number(p.close),
    volume: p.volume,
  }))
}

/**
 * 종목 상세 화면의 일봉 close 추세 라인 차트.
 *
 * Recharts 는 manualChunks 의 `vendor-charts` 청크에 격리되어 있고, 본 컴포넌트를
 * 사용하는 StockDetail 페이지 자체가 router 레벨에서 React.lazy 로드되므로
 * 이 모듈도 동일 chunk 와 함께 lazy 로드된다. (별도 lazy wrap 불필요.)
 */
export function PriceChart({ prices, height = 240, className }: PriceChartProps) {
  const points = useMemo(() => buildPoints(prices), [prices])

  if (points.length === 0) {
    return (
      <div
        data-testid="price-chart-empty"
        className={cn(
          'flex items-center justify-center rounded-md border border-dashed border-border bg-card p-6 text-sm text-muted-foreground',
          className,
        )}
        style={{ height }}
      >
        표시할 일봉 데이터가 없습니다.
      </div>
    )
  }

  return (
    <div
      data-testid="price-chart"
      className={cn('w-full', className)}
      style={{ height }}
    >
      <ResponsiveContainer width="100%" height={height}>
        <LineChart
          data={points}
          margin={{ top: 8, right: 16, bottom: 8, left: 8 }}
        >
          <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
          <XAxis
            dataKey="date"
            tick={{ fontSize: 11, fill: 'hsl(var(--muted-foreground))' }}
            tickLine={false}
            minTickGap={32}
          />
          <YAxis
            tick={{ fontSize: 11, fill: 'hsl(var(--muted-foreground))' }}
            tickLine={false}
            width={64}
            domain={['auto', 'auto']}
          />
          <Tooltip
            contentStyle={{
              background: 'hsl(var(--card))',
              border: '1px solid hsl(var(--border))',
              borderRadius: 6,
              fontSize: 12,
            }}
            formatter={(value: number | string) =>
              typeof value === 'number' ? value.toLocaleString('ko-KR') : value
            }
          />
          <Line
            type="monotone"
            dataKey="close"
            stroke="hsl(var(--primary))"
            strokeWidth={2}
            dot={false}
            activeDot={{ r: 4 }}
            isAnimationActive={false}
            connectNulls
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}
