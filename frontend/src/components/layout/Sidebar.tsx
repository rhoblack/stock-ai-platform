import { NavLink } from 'react-router-dom'
import {
  Activity,
  BarChart3,
  History,
  LayoutDashboard,
  ListTree,
  ScrollText,
  Search,
  Settings as SettingsIcon,
  type LucideIcon,
} from 'lucide-react'
import { cn } from '@/lib/utils'

interface NavItem {
  to: string
  label: string
  Icon: LucideIcon
  matchPrefix?: string
}

// 8 v0.2 dashboard menus.
const NAV_ITEMS: NavItem[] = [
  { to: '/today', label: '오늘의 리포트', Icon: LayoutDashboard },
  { to: '/recommendations', label: '추천 종목', Icon: BarChart3 },
  { to: '/recommendations/history', label: '추천 이력', Icon: History },
  { to: '/holdings', label: '보유 종목 점검', Icon: ListTree },
  { to: '/stocks', label: '종목 상세', Icon: Search, matchPrefix: '/stocks' },
  { to: '/universe/market-cap-top', label: '시가총액 TOP', Icon: Activity },
  { to: '/jobs', label: '시스템 로그 / 잡', Icon: ScrollText, matchPrefix: '/jobs' },
  { to: '/settings', label: '설정', Icon: SettingsIcon },
]

export function Sidebar() {
  return (
    <aside className="flex h-full w-60 shrink-0 flex-col border-r border-border bg-card">
      <div className="flex items-center gap-2 px-5 py-4">
        <div className="flex h-8 w-8 items-center justify-center rounded-md bg-primary text-primary-foreground text-xs font-semibold">
          AI
        </div>
        <div className="flex flex-col leading-tight">
          <span className="text-sm font-semibold">Stock AI</span>
          <span className="text-xs text-muted-foreground">v0.2 dashboard</span>
        </div>
      </div>
      <nav className="flex flex-col gap-1 px-3 pb-4 pt-2" aria-label="primary">
        {NAV_ITEMS.map(({ to, label, Icon }) => (
          <NavLink
            key={to}
            to={to}
            end={to === '/recommendations'}
            className={({ isActive }) =>
              cn(
                'flex items-center gap-2 rounded-md px-3 py-2 text-sm transition-colors',
                'hover:bg-accent hover:text-accent-foreground',
                isActive && 'bg-accent text-accent-foreground font-medium',
              )
            }
          >
            <Icon className="h-4 w-4" aria-hidden />
            <span>{label}</span>
          </NavLink>
        ))}
      </nav>
      <div className="mt-auto px-5 py-4 text-xs text-muted-foreground">
        <p>v0.1-backend-final 소비 (read-only)</p>
        <p className="mt-1">자동매매 / 실 주문 미포함</p>
      </div>
    </aside>
  )
}
