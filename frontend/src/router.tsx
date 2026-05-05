import { Navigate, Route, Routes } from 'react-router-dom'
import { AppLayout } from './components/layout/AppLayout'
import { TodayReportPage } from './pages/TodayReport'
import { RecommendationsPage } from './pages/Recommendations'
import { RecommendationHistoryPage } from './pages/RecommendationHistory'
import { HoldingsPage } from './pages/Holdings'
import { StockDetailPage } from './pages/StockDetail'
import { MarketCapTopPage } from './pages/MarketCapTop'
import { JobsPage } from './pages/Jobs'
import { SettingsPage } from './pages/Settings'

// v0.2 Phase A는 loader / action 을 쓰지 않으므로 legacy non-data router
// (`<Routes>` / `<Route>`) 로 충분. 후속 phase 에서 데이터 라우터로 옮길
// 필요가 생기면 그때 createBrowserRouter 로 전환.
export function AppRoutes() {
  return (
    <Routes>
      <Route path="/" element={<AppLayout />}>
        <Route index element={<Navigate to="/today" replace />} />
        <Route path="today" element={<TodayReportPage />} />
        <Route path="recommendations" element={<RecommendationsPage />} />
        <Route path="recommendations/history" element={<RecommendationHistoryPage />} />
        <Route path="recommendations/runs/:runId" element={<RecommendationsPage />} />
        <Route path="holdings" element={<HoldingsPage />} />
        <Route path="stocks" element={<StockDetailPage />} />
        <Route path="stocks/:symbol" element={<StockDetailPage />} />
        <Route path="universe/market-cap-top" element={<MarketCapTopPage />} />
        <Route path="jobs" element={<JobsPage />} />
        <Route path="jobs/:jobId" element={<JobsPage />} />
        <Route path="settings" element={<SettingsPage />} />
        <Route path="*" element={<Navigate to="/today" replace />} />
      </Route>
    </Routes>
  )
}
