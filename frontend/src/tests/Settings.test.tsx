import { describe, expect, it } from 'vitest'
import { screen, waitFor, within } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { renderWithProviders } from './renderWithProviders'
import { server } from './mswServer'
import { SettingsPage } from '@/pages/Settings'

describe('SettingsPage', () => {
  it('shows app/KIS/Telegram/safety sections + freeze banner (happy)', async () => {
    // Default mswServer handler covers a happy masked response.
    renderWithProviders(<SettingsPage />, { initialEntries: ['/settings'] })

    await waitFor(() =>
      expect(screen.getByTestId('settings-app-grid')).toBeInTheDocument(),
    )

    // Freeze banner present
    expect(screen.getByTestId('settings-freeze-banner')).toHaveTextContent(
      'v0.1 백엔드 동결',
    )

    // 4 sections rendered
    expect(screen.getByTestId('settings-app-grid')).toBeInTheDocument()
    expect(screen.getByTestId('settings-kis-grid')).toBeInTheDocument()
    expect(screen.getByTestId('settings-telegram-grid')).toBeInTheDocument()
    expect(screen.getByTestId('settings-safety-grid')).toBeInTheDocument()

    // 5 v0.1 안전 플래그 모두 false / unmasked-safe
    for (const flag of [
      'feature_real_order_execution',
      'feature_full_auto',
      'feature_paper_trading',
      'feature_backtest',
      'feature_custom_ai_training',
    ]) {
      const badge = screen.getByTestId(`safety-${flag}`)
      expect(badge).toHaveTextContent('false')
      expect(badge).toHaveAttribute('data-danger', 'false')
    }

    // kis_use_paper=true → safe (dangerWhen='false', enabled=true → not danger)
    expect(screen.getByTestId('safety-kis_use_paper')).toHaveAttribute(
      'data-danger',
      'false',
    )
    // telegram_enabled=false → safe (dangerWhen='true', enabled=false)
    expect(screen.getByTestId('safety-telegram_enabled')).toHaveAttribute(
      'data-danger',
      'false',
    )
  })

  it('renders all secret values masked (no plaintext)', async () => {
    renderWithProviders(<SettingsPage />, { initialEntries: ['/settings'] })

    await waitFor(() =>
      expect(screen.getByTestId('settings-kis-grid')).toBeInTheDocument(),
    )

    for (const label of [
      'kis_app_key',
      'kis_app_secret',
      'kis_account_no',
      'telegram_bot_token',
      'telegram_chat_id',
    ]) {
      const node = screen.getByTestId(`secret-${label}`)
      expect(node).toHaveAttribute('data-masked', 'true')
      expect(node).toHaveTextContent('*')
      expect(node).not.toHaveTextContent(/⚠ unmasked/)
    }
  })

  it('flags secrets as unmasked when backend mistakenly returns plaintext', async () => {
    // Hypothetical regression: backend forgets to mask. Frontend should
    // visually mark the value with ⚠ unmasked so the operator notices.
    server.use(
      http.get('*/api/settings', () =>
        HttpResponse.json({
          app_env: 'test',
          app_name: 'stock_ai_platform',
          timezone: 'Asia/Seoul',
          log_level: 'INFO',
          telegram_enabled: false,
          telegram_bot_token: 'PLAINTEXT_NEVER_OK',
          telegram_chat_id: '12****90',
          kis_app_key: 'PSnm****Zqry',
          kis_app_secret: 'XxC8****4yc=',
          kis_account_no: '5015****1-01',
          kis_use_paper: true,
          scheduler_enabled: false,
          feature_real_order_execution: false,
          feature_full_auto: false,
          feature_paper_trading: false,
          feature_backtest: false,
          feature_custom_ai_training: false,
        }),
      ),
    )

    renderWithProviders(<SettingsPage />, { initialEntries: ['/settings'] })
    await waitFor(() =>
      expect(screen.getByTestId('secret-telegram_bot_token')).toBeInTheDocument(),
    )
    const node = screen.getByTestId('secret-telegram_bot_token')
    expect(node).toHaveAttribute('data-masked', 'false')
    expect(within(node).getByText(/⚠ unmasked/)).toBeInTheDocument()
  })

  it('flags safety violations red when feature_real_order_execution=true', async () => {
    server.use(
      http.get('*/api/settings', () =>
        HttpResponse.json({
          app_env: 'test',
          app_name: 'stock_ai_platform',
          timezone: 'Asia/Seoul',
          log_level: 'INFO',
          telegram_enabled: false,
          telegram_bot_token: 'fake****test',
          telegram_chat_id: '12****90',
          kis_app_key: 'PSnm****Zqry',
          kis_app_secret: 'XxC8****4yc=',
          kis_account_no: '5015****1-01',
          kis_use_paper: false,
          scheduler_enabled: false,
          feature_real_order_execution: true,
          feature_full_auto: false,
          feature_paper_trading: false,
          feature_backtest: false,
          feature_custom_ai_training: false,
        }),
      ),
    )

    renderWithProviders(<SettingsPage />, { initialEntries: ['/settings'] })
    await waitFor(() =>
      expect(screen.getByTestId('safety-feature_real_order_execution')).toHaveAttribute(
        'data-danger',
        'true',
      ),
    )
    // kis_use_paper=false → danger (since dangerWhen='false')
    expect(screen.getByTestId('safety-kis_use_paper')).toHaveAttribute(
      'data-danger',
      'true',
    )
    // 위험 카운트가 헤더에 노출
    expect(screen.getByText(/⚠ 1건 위험 상태/)).toBeInTheDocument()
  })

  it('shows error state on 500', async () => {
    server.use(
      http.get('*/api/settings', () =>
        HttpResponse.json({ detail: 'simulated outage' }, { status: 500 }),
      ),
    )

    renderWithProviders(<SettingsPage />, { initialEntries: ['/settings'] })
    await waitFor(() =>
      expect(screen.getByTestId('settings-error')).toBeInTheDocument(),
    )
    // 빨간 에러 박스라도 freeze 배너는 그대로 노출 (운영자에게 정책 안내 유지)
    expect(screen.getByTestId('settings-freeze-banner')).toBeInTheDocument()
  })
})
