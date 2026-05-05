import { useNavigate, useParams } from 'react-router-dom'
import type { Holding, HoldingCheck } from '@/api/types'
import { DecisionPill } from '@/components/common/DecisionPill'
import { RiskBadge } from '@/components/common/RiskBadge'
import { ReturnRate } from '@/components/common/ReturnRate'
import { cn } from '@/lib/utils'

interface HoldingsListProps {
  holdings: Holding[]
  latestChecksBySymbol: Map<string, HoldingCheck>
}

export function HoldingsList({ holdings, latestChecksBySymbol }: HoldingsListProps) {
  const navigate = useNavigate()
  const { symbol: selectedSymbol } = useParams<{ symbol: string }>()

  if (holdings.length === 0) {
    return (
      <div
        data-testid="holdings-empty"
        className="rounded-lg border border-dashed border-border bg-card p-6 text-sm text-muted-foreground"
      >
        활성 보유 종목이 없습니다.
      </div>
    )
  }

  return (
    <div className="overflow-x-auto rounded-lg border border-border bg-card">
      <table className="w-full text-sm" data-testid="holdings-table">
        <thead className="bg-muted/40 text-left text-xs uppercase tracking-wide text-muted-foreground">
          <tr>
            <th className="px-3 py-2 font-medium">symbol</th>
            <th className="px-3 py-2 font-medium">qty</th>
            <th className="px-3 py-2 font-medium">avg_buy</th>
            <th className="px-3 py-2 font-medium">strategy</th>
            <th className="px-3 py-2 font-medium">latest decision</th>
            <th className="px-3 py-2 font-medium">risk</th>
            <th className="px-3 py-2 font-medium">return</th>
            <th className="px-3 py-2 font-medium">alert</th>
          </tr>
        </thead>
        <tbody>
          {holdings.map(holding => {
            const check = latestChecksBySymbol.get(holding.symbol)
            const isActive = selectedSymbol === holding.symbol
            return (
              <tr
                key={holding.id}
                data-testid={`holding-row-${holding.symbol}`}
                className={cn(
                  'cursor-pointer border-t border-border transition-colors hover:bg-accent',
                  isActive && 'bg-accent',
                )}
                onClick={() => navigate(`/holdings/${holding.symbol}`)}
              >
                <td className="px-3 py-2 font-mono text-sm">{holding.symbol}</td>
                <td className="px-3 py-2 font-mono tabular-nums text-xs">
                  {holding.quantity ?? '—'}
                </td>
                <td className="px-3 py-2 font-mono tabular-nums text-xs">
                  {holding.avg_buy_price ?? '—'}
                </td>
                <td className="px-3 py-2 text-xs text-muted-foreground">
                  {holding.strategy_type ?? '—'}
                </td>
                <td className="px-3 py-2">
                  <DecisionPill decision={check?.decision} />
                </td>
                <td className="px-3 py-2">
                  <RiskBadge level={check?.risk_level} flags={check?.risk_flags} />
                </td>
                <td className="px-3 py-2">
                  <ReturnRate value={check?.return_rate ?? null} />
                </td>
                <td className="px-3 py-2 text-xs">
                  {check?.alert ? (
                    <span
                      data-testid={`holding-alert-${holding.symbol}`}
                      className="text-red-600 dark:text-red-300"
                    >
                      ⚠ alert
                    </span>
                  ) : (
                    <span className="text-muted-foreground">—</span>
                  )}
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
