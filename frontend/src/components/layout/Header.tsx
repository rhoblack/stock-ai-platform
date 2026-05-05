import { useLocation } from 'react-router-dom'
import { Moon, Sun } from 'lucide-react'
import { useHealth } from '@/hooks/useHealth'
import { useTheme } from '../theme/ThemeProvider'
import { cn } from '@/lib/utils'

const PAGE_TITLES: Array<[string, string]> = [
  ['/today', '오늘의 리포트'],
  ['/recommendations/history', '추천 이력'],
  ['/recommendations', '추천 종목'],
  ['/holdings', '보유 종목 점검'],
  ['/stocks', '종목 상세'],
  ['/universe/market-cap-top', '시가총액 TOP'],
  ['/jobs', '시스템 로그 / 잡'],
  ['/settings', '설정'],
]

function resolveTitle(pathname: string): string {
  for (const [prefix, title] of PAGE_TITLES) {
    if (pathname === prefix || pathname.startsWith(`${prefix}/`)) {
      return title
    }
  }
  return 'Stock AI Dashboard'
}

export function Header() {
  const { pathname } = useLocation()
  const title = resolveTitle(pathname)
  const { theme, toggle } = useTheme()
  const health = useHealth()

  let badgeColor = 'bg-muted-foreground'
  let badgeLabel = '연결 중…'
  if (health.isError) {
    badgeColor = 'bg-destructive'
    badgeLabel = '백엔드 연결 실패'
  } else if (health.isSuccess) {
    badgeColor = 'bg-emerald-500'
    badgeLabel = `OK · ${health.data.app} · ${health.data.env}`
  }

  return (
    <header className="flex items-center justify-between border-b border-border bg-card px-6 py-3">
      <div className="flex flex-col leading-tight">
        <span className="text-xs uppercase tracking-wide text-muted-foreground">
          v0.2 Phase A
        </span>
        <h1 className="text-lg font-semibold">{title}</h1>
      </div>
      <div className="flex items-center gap-3">
        <div
          className="flex items-center gap-2 rounded-md border border-border px-3 py-1.5 text-xs"
          aria-label="backend health"
          data-testid="health-badge"
        >
          <span className={cn('h-2 w-2 rounded-full', badgeColor)} aria-hidden />
          <span className="text-muted-foreground">{badgeLabel}</span>
        </div>
        <button
          type="button"
          aria-label="테마 전환"
          className="inline-flex h-8 w-8 items-center justify-center rounded-md border border-border hover:bg-accent"
          onClick={toggle}
        >
          {theme === 'dark' ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
        </button>
      </div>
    </header>
  )
}
