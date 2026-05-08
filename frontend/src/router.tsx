import { lazy } from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'
import { AppLayout } from './components/layout/AppLayout'

// v0.2 Phase F: 모든 페이지를 React.lazy 로 분리해 페이지 단위 코드 스플릿.
// Recharts (RecommendationHistory, Holdings) / TanStack Table 가 무거워
// 첫 진입 번들에서 분리되도록 한다. 페이지는 named export 를 그대로 두고
// router 만 lazy chunk 로 진입하도록 wrap.
const TodayReportPage = lazy(() =>
  import('./pages/TodayReport').then(m => ({ default: m.TodayReportPage })),
)
const RecommendationsPage = lazy(() =>
  import('./pages/Recommendations').then(m => ({ default: m.RecommendationsPage })),
)
const RecommendationHistoryPage = lazy(() =>
  import('./pages/RecommendationHistory').then(m => ({
    default: m.RecommendationHistoryPage,
  })),
)
const HoldingsPage = lazy(() =>
  import('./pages/Holdings').then(m => ({ default: m.HoldingsPage })),
)
const StockDetailPage = lazy(() =>
  import('./pages/StockDetail').then(m => ({ default: m.StockDetailPage })),
)
const MarketCapTopPage = lazy(() =>
  import('./pages/MarketCapTop').then(m => ({ default: m.MarketCapTopPage })),
)
const JobsPage = lazy(() =>
  import('./pages/Jobs').then(m => ({ default: m.JobsPage })),
)
const SettingsPage = lazy(() =>
  import('./pages/Settings').then(m => ({ default: m.SettingsPage })),
)
const ThemesPage = lazy(() =>
  import('./pages/Themes').then(m => ({ default: m.ThemesPage })),
)
const ThemeDetailPage = lazy(() =>
  import('./pages/ThemeDetail').then(m => ({ default: m.ThemeDetailPage })),
)
const BacktestPage = lazy(() =>
  import('./pages/Backtest').then(m => ({ default: m.BacktestPage })),
)
// v0.8 Phase D
const WatchlistPage = lazy(() =>
  import('./pages/Watchlist').then(m => ({ default: m.WatchlistPage })),
)
const LoginPage = lazy(() =>
  import('./pages/Login').then(m => ({ default: m.LoginPage })),
)
// v0.13 Phase D
const ValidationPage = lazy(() =>
  import('./pages/Validation').then(m => ({ default: m.ValidationPage })),
)
// v0.14 Phase E — Paper / Simulation Trading dashboard.
const PaperTradingPage = lazy(() =>
  import('./pages/PaperTrading').then(m => ({ default: m.PaperTradingPage })),
)

export function AppRoutes() {
  return (
    <Routes>
      {/* v0.8 Phase D: /login lives outside AppLayout (no sidebar/header) */}
      <Route path="/login" element={<LoginPage />} />

      <Route path="/" element={<AppLayout />}>
        <Route index element={<Navigate to="/today" replace />} />
        <Route path="today" element={<TodayReportPage />} />
        <Route path="recommendations" element={<RecommendationsPage />} />
        <Route path="recommendations/history" element={<RecommendationHistoryPage />} />
        <Route path="recommendations/runs/:runId" element={<RecommendationsPage />} />
        <Route path="holdings" element={<HoldingsPage />} />
        <Route path="holdings/:symbol" element={<HoldingsPage />} />
        <Route path="stocks" element={<StockDetailPage />} />
        <Route path="stocks/:symbol" element={<StockDetailPage />} />
        <Route path="universe/market-cap-top" element={<MarketCapTopPage />} />
        <Route path="themes" element={<ThemesPage />} />
        <Route path="themes/:themeId" element={<ThemeDetailPage />} />
        <Route path="backtest" element={<BacktestPage />} />
        <Route path="watchlist" element={<WatchlistPage />} />
        <Route path="validation" element={<ValidationPage />} />
        <Route path="paper" element={<PaperTradingPage />} />
        <Route path="jobs" element={<JobsPage />} />
        <Route path="jobs/:jobId" element={<JobsPage />} />
        <Route path="settings" element={<SettingsPage />} />
        <Route path="*" element={<Navigate to="/today" replace />} />
      </Route>
    </Routes>
  )
}
