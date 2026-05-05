import type { ReactNode } from 'react'
import { describe, expect, it } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ThemeProvider } from '@/components/theme/ThemeProvider'
import { AppRoutes } from '@/router'

function renderApp(initialPath = '/today') {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false, staleTime: Infinity } },
  })
  function wrapper({ children }: { children: ReactNode }) {
    return (
      <QueryClientProvider client={qc}>
        <ThemeProvider>
          <MemoryRouter initialEntries={[initialPath]}>{children}</MemoryRouter>
        </ThemeProvider>
      </QueryClientProvider>
    )
  }
  return render(<AppRoutes />, { wrapper })
}

describe('App routes shell', () => {
  it('renders sidebar with all 8 dashboard menus', () => {
    renderApp()
    // 사이드바와 헤더 둘 다 "오늘의 리포트" 를 노출하므로 getAllByText.
    expect(screen.getAllByText('오늘의 리포트').length).toBeGreaterThanOrEqual(1)
    expect(screen.getByText('추천 종목')).toBeInTheDocument()
    expect(screen.getByText('추천 이력')).toBeInTheDocument()
    expect(screen.getByText('보유 종목 점검')).toBeInTheDocument()
    expect(screen.getByText('종목 상세')).toBeInTheDocument()
    expect(screen.getByText('시가총액 TOP')).toBeInTheDocument()
    expect(screen.getByText('시스템 로그 / 잡')).toBeInTheDocument()
    expect(screen.getByText('설정')).toBeInTheDocument()
  })

  it('redirects "/" to "/today" so default landing shows today report header', () => {
    renderApp('/')
    expect(screen.getAllByText('오늘의 리포트').length).toBeGreaterThanOrEqual(2)
  })

  it('shows OK health badge after /health resolves', async () => {
    renderApp()
    await waitFor(() => {
      expect(screen.getByTestId('health-badge')).toHaveTextContent('OK')
    })
  })
})
