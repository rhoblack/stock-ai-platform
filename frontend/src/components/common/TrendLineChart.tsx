import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { cn } from '@/lib/utils'

interface TrendLineChartProps<T extends object> {
  data: T[]
  xKey: keyof T & string
  yKey: keyof T & string
  label?: string
  height?: number
  className?: string
  unit?: string
  testid?: string
}

export function TrendLineChart<T extends object>({
  data,
  xKey,
  yKey,
  label,
  height = 220,
  className,
  unit = '',
  testid = 'trend-chart',
}: TrendLineChartProps<T>) {
  if (data.length === 0) {
    return (
      <div
        data-testid={`${testid}-empty`}
        className={cn(
          'flex items-center justify-center rounded-md border border-dashed border-border bg-card p-6 text-sm text-muted-foreground',
          className,
        )}
        style={{ height }}
      >
        표시할 데이터가 없습니다.
      </div>
    )
  }
  return (
    <div data-testid={testid} className={cn('w-full', className)} style={{ height }}>
      {label ? (
        <p className="mb-2 text-xs uppercase tracking-wide text-muted-foreground">
          {label}
        </p>
      ) : null}
      <ResponsiveContainer width="100%" height={label ? height - 24 : height}>
        <LineChart data={data} margin={{ top: 8, right: 16, bottom: 8, left: 8 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
          <XAxis
            dataKey={xKey}
            tick={{ fontSize: 11, fill: 'hsl(var(--muted-foreground))' }}
            tickLine={false}
          />
          <YAxis
            tick={{ fontSize: 11, fill: 'hsl(var(--muted-foreground))' }}
            tickLine={false}
            width={48}
            unit={unit}
          />
          <Tooltip
            contentStyle={{
              background: 'hsl(var(--card))',
              border: '1px solid hsl(var(--border))',
              borderRadius: 6,
              fontSize: 12,
            }}
            formatter={(value: number | string) =>
              typeof value === 'number' ? `${value.toFixed(2)}${unit}` : value
            }
          />
          <Line
            type="monotone"
            dataKey={yKey}
            stroke="hsl(var(--primary))"
            strokeWidth={2}
            dot={{ r: 3 }}
            activeDot={{ r: 5 }}
            isAnimationActive={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}
