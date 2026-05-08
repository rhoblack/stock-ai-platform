import { test, expect } from '@playwright/test'
import { installApiMocks } from './fixtures/apiMocks'

test.beforeEach(async ({ page }) => {
  await installApiMocks(page)
})

test.describe('v0.2 Phase F — dashboard happy paths (9 screens, mocked API)', () => {
  test('all 15 sidebar menus are reachable and render their main content', async ({
    page,
  }) => {
    await page.goto('/')
    // Default redirect → /today
    await expect(
      page.getByRole('heading', { name: '오늘의 리포트', level: 2 }),
    ).toBeVisible()

    // 사이드바 nav 영역으로 selector 를 좁혀 페이지 내 동명 링크 ("전체 →" 등)
    // 와의 충돌을 피한다.
    const nav = page.getByRole('navigation', { name: 'primary' })

    await nav.getByRole('link', { name: '추천 종목' }).click()
    await expect(page.getByTestId('rec-metric-run-date')).toBeVisible()

    await nav.getByRole('link', { name: '추천 이력' }).click()
    await expect(page.getByTestId('history-trend-success')).toBeVisible()

    await nav.getByRole('link', { name: '보유 종목 점검' }).click()
    await expect(page.getByTestId('holding-row-005930')).toBeVisible()

    await nav.getByRole('link', { name: '종목 상세' }).click()
    await expect(page.getByText(/종목 코드가 지정되지 않았습니다/)).toBeVisible()

    await nav.getByRole('link', { name: '시가총액 TOP' }).click()
    await expect(page.getByTestId('mcap-row-005930')).toBeVisible()

    await nav.getByRole('link', { name: '테마 (β)' }).click()
    await expect(page.getByTestId('theme-row-41')).toBeVisible()

    await nav.getByRole('link', { name: '백테스트 (β)' }).click()
    await expect(page.getByTestId('backtest-strategies')).toBeVisible()

    // v0.8 Phase D — 관심종목
    await nav.getByRole('link', { name: '관심종목' }).click()
    await expect(page.getByTestId('watchlist-page')).toBeVisible()

    // v0.13 Phase D — 검증 리포트
    await nav.getByRole('link', { name: '검증 리포트' }).click()
    await expect(page.getByTestId('validation-page')).toBeVisible()

    // v0.14 Phase E — 페이퍼 트레이딩 (β)
    await nav.getByRole('link', { name: '페이퍼 트레이딩 (β)' }).click()
    await expect(page.getByTestId('paper-page')).toBeVisible()

    // v0.15 Phase E — 승인 대기 (β)
    await nav.getByRole('link', { name: '승인 대기 (β)' }).click()
    await expect(page.getByTestId('approvals-page')).toBeVisible()

    // v0.16 Phase E — 실주문 준비 (β)
    await nav.getByRole('link', { name: '실주문 준비 (β)' }).click()
    await expect(page.getByTestId('real-orders-page')).toBeVisible()

    await nav.getByRole('link', { name: '시스템 로그 / 잡' }).click()
    await expect(page.getByTestId('job-row-101')).toBeVisible()

    await nav.getByRole('link', { name: '설정' }).click()
    await expect(page.getByTestId('settings-freeze-banner')).toBeVisible()

    await nav.getByRole('link', { name: '오늘의 리포트' }).click()
    await expect(page.getByTestId('today-top-recs')).toBeVisible()
  })

  test('MarketStatusBanner is visible on Today / Jobs / Holdings pages', async ({
    page,
  }) => {
    for (const path of ['/today', '/jobs', '/holdings']) {
      await page.goto(path)
      const banner = page.getByTestId('market-status-banner')
      await expect(banner).toBeVisible()
      await expect(banner).toHaveAttribute('data-state', /open|holiday|weekend/)
    }
  })

  test('Jobs row click reveals result_summary JSON in detail panel', async ({
    page,
  }) => {
    await page.goto('/jobs')
    await page.getByTestId('job-row-101').click()
    await expect(page).toHaveURL(/\/jobs\/101$/)
    const json = page.getByTestId('json-viewer').first()
    await expect(json).toContainText('"notification_status": "DRY_RUN"')
    await expect(json).toContainText('"dry_run": true')
    await expect(json).toContainText('"run_id": 7')
  })

  test('StockDetail price chart card and days selector are visible', async ({
    page,
  }) => {
    await page.goto('/stocks/005930')
    const card = page.getByTestId('stock-detail-price-chart')
    await expect(card).toBeVisible()
    // 차트 본체 (count > 0) 가 fixture 에서 5건 → empty placeholder 가 아닌
    // price-chart 가 노출되어야 한다.
    await expect(page.getByTestId('price-chart')).toBeVisible()
    await expect(page.getByTestId('price-chart-empty')).toHaveCount(0)
    // 기본 120d 가 active.
    await expect(page.getByTestId('price-chart-days-120')).toHaveAttribute(
      'data-active',
      'true',
    )
    // 30d 클릭 시 active 토글.
    await page.getByTestId('price-chart-days-30').click()
    await expect(page.getByTestId('price-chart-days-30')).toHaveAttribute(
      'data-active',
      'true',
    )
  })

  test('StockDetail analyst report cards expose safe read-only summaries', async ({
    page,
  }) => {
    await page.goto('/stocks/005930')
    await expect(page.getByTestId('stock-detail-consensus')).toBeVisible()
    await expect(page.getByTestId('stock-detail-analyst-reports')).toContainText(
      '삼성전자 HBM 수요 회복',
    )
    await expect(page.getByTestId('stock-detail-related-themes')).toContainText('HBM')
    await expect(page.getByTestId('stock-detail-signal-events')).toContainText(
      'SUPPLY_SHORTAGE',
    )
    await expect(page.getByText(/source_file_path/)).toHaveCount(0)
    await expect(page.getByText(/D:\/private/)).toHaveCount(0)

    const payload = await page.evaluate(async () => {
      const response = await fetch('/api/stocks/005930')
      return response.json()
    })
    expect(JSON.stringify(payload)).not.toContain('source_file_path')
  })

  test('MarketCap TOP filter switches from KOSPI to KOSDAQ to ALL', async ({
    page,
  }) => {
    await page.goto('/universe/market-cap-top')
    await expect(page.getByTestId('mcap-row-005930')).toBeVisible()
    await expect(page.getByTestId('mcap-row-247540')).toHaveCount(0)

    await page.getByTestId('mcap-filter-KOSDAQ').click()
    await expect(page.getByTestId('mcap-row-247540')).toBeVisible()
    await expect(page.getByTestId('mcap-row-005930')).toHaveCount(0)

    await page.getByTestId('mcap-filter-ALL').click()
    await expect(page.getByTestId('mcap-row-005930')).toBeVisible()
    await expect(page.getByTestId('mcap-row-247540')).toBeVisible()
  })

  test('MarketCap TOP search filters by name/symbol', async ({ page }) => {
    await page.goto('/universe/market-cap-top')
    await expect(page.getByTestId('mcap-row-005930')).toBeVisible()
    await page.getByTestId('mcap-search').fill('SK')
    await expect(page.getByTestId('mcap-row-000660')).toBeVisible()
    await expect(page.getByTestId('mcap-row-005930')).toHaveCount(0)
  })

  test('Settings shows the read-only Provider Health panel (v0.10 Phase D)', async ({
    page,
  }) => {
    await page.goto('/settings')
    await expect(page.getByTestId('provider-health-panel')).toBeVisible()
    await expect(page.getByTestId('provider-health-table')).toBeVisible()
    // Canonical 3 rows always surface.
    await expect(page.getByTestId('provider-row-kis')).toBeVisible()
    await expect(page.getByTestId('provider-row-dart')).toBeVisible()
    await expect(page.getByTestId('provider-row-rss')).toBeVisible()

    // DART / RSS default-OFF in the e2e fixture.
    await expect(page.getByTestId('provider-row-dart')).toHaveAttribute(
      'data-enabled',
      'false',
    )
    await expect(page.getByTestId('provider-row-dart')).toHaveAttribute(
      'data-configured',
      'false',
    )
    await expect(page.getByTestId('provider-row-rss')).toHaveAttribute(
      'data-enabled',
      'false',
    )
    await expect(page.getByTestId('provider-enabled-dart')).toContainText(
      'disabled',
    )
    await expect(page.getByTestId('provider-configured-rss')).toContainText(
      'not_configured',
    )

    // Read-only — no buttons inside the panel, no enable/disable toggle.
    const buttonsInsidePanel = await page
      .getByTestId('provider-health-panel')
      .locator('button, [role="switch"], input[type="checkbox"]')
      .count()
    expect(buttonsInsidePanel).toBe(0)

    // Forbidden secret substrings absent from page text + raw API payload.
    for (const forbidden of [
      'crtfc_key',
      'dart_api_key',
      'last_error_message',
    ]) {
      await expect(page.getByText(forbidden)).toHaveCount(0)
    }
    const payload = await page.evaluate(async () => {
      const r = await fetch('/api/health/providers')
      return r.json()
    })
    const raw = JSON.stringify(payload)
    for (const forbidden of [
      'crtfc_key',
      'dart_api_key',
      'rss_feed_urls',
      'kis_app_secret',
      'last_error_message',
      'access_token',
      'password',
    ]) {
      expect(raw).not.toContain(forbidden)
    }
  })

  test('Settings Provider Health panel surfaces v0.11 Phase D 24h aggregates and recent failures', async ({
    page,
  }) => {
    await page.goto('/settings')
    await expect(page.getByTestId('provider-health-panel')).toBeVisible()
    await expect(page.getByTestId('provider-health-table')).toBeVisible()

    // KIS fixture: 50 calls, 49 success, success_rate=0.98, 1 TIMEOUT failure.
    await expect(page.getByTestId('provider-success-rate-kis')).toBeVisible()
    await expect(page.getByTestId('provider-success-rate-kis')).toContainText(
      '98.0%',
    )
    await expect(page.getByTestId('provider-avg-attempts-kis')).toContainText(
      '1.05',
    )

    // DART/RSS unregistered → success-rate placeholder shows the dash.
    await expect(page.getByTestId('provider-success-rate-dart')).toContainText(
      '—',
    )
    await expect(page.getByTestId('provider-avg-attempts-rss')).toContainText(
      '—',
    )

    // Recent failures section: only KIS has a failure in the fixture.
    await expect(
      page.getByTestId('provider-recent-failures-section'),
    ).toBeVisible()
    await expect(
      page.getByTestId('provider-recent-failures-card-kis'),
    ).toBeVisible()
    await expect(
      page.getByTestId('provider-recent-failure-kis-0'),
    ).toContainText('TIMEOUT')

    // DART / RSS have empty recent_failures so their cards do not render.
    await expect(
      page.getByTestId('provider-recent-failures-card-dart'),
    ).toHaveCount(0)
    await expect(
      page.getByTestId('provider-recent-failures-card-rss'),
    ).toHaveCount(0)

    // Read-only: panel still has 0 buttons / switches / checkboxes.
    const buttonsInsidePanel = await page
      .getByTestId('provider-health-panel')
      .locator('button, [role="switch"], input[type="checkbox"]')
      .count()
    expect(buttonsInsidePanel).toBe(0)

    // Phase D paranoid secret scan: page text + raw payload free of
    // last_error_message / api_key / etc.
    for (const forbidden of [
      'crtfc_key',
      'dart_api_key',
      'last_error_message',
      'feed_url',
    ]) {
      await expect(page.getByText(forbidden)).toHaveCount(0)
    }
    const payload = await page.evaluate(async () => {
      const r = await fetch('/api/health/providers')
      return r.json()
    })
    const raw = JSON.stringify(payload)
    for (const forbidden of [
      'crtfc_key',
      'dart_api_key',
      'rss_feed_urls',
      'kis_app_secret',
      'last_error_message',
      'access_token',
      'password',
      '?api_key=',
    ]) {
      expect(raw).not.toContain(forbidden)
    }
  })

  test('Settings shows masked secrets only — no plaintext leak', async ({ page }) => {
    await page.goto('/settings')
    await expect(page.getByTestId('settings-freeze-banner')).toBeVisible()

    // 모든 비밀 노드가 data-masked="true"
    for (const label of [
      'kis_app_key',
      'kis_app_secret',
      'kis_account_no',
      'telegram_bot_token',
      'telegram_chat_id',
    ]) {
      const node = page.getByTestId(`secret-${label}`)
      await expect(node).toBeVisible()
      await expect(node).toHaveAttribute('data-masked', 'true')
      await expect(node).toContainText('*')
      await expect(node).not.toContainText('⚠ unmasked')
    }

    // 페이지 어디에도 "⚠ unmasked" 가 보이지 않아야 한다
    await expect(page.getByText('⚠ unmasked')).toHaveCount(0)

    // 5개 v0.1 안전 플래그 모두 false (data-danger='false')
    for (const flag of [
      'feature_real_order_execution',
      'feature_full_auto',
      'feature_paper_trading',
      'feature_backtest',
      'feature_custom_ai_training',
    ]) {
      await expect(page.getByTestId(`safety-${flag}`)).toHaveAttribute(
        'data-danger',
        'false',
      )
    }
  })

  test('Themes ranking + detail expose read-only summaries; theme link from StockDetail navigates', async ({
    page,
  }) => {
    await page.goto('/themes')
    await expect(page.getByTestId('themes-table')).toBeVisible()
    await expect(page.getByTestId('theme-row-41')).toBeVisible()
    await expect(page.getByTestId('theme-row-42')).toBeVisible()
    await expect(page.getByTestId('theme-mapping-count-41')).toContainText('2')
    await expect(page.getByTestId('theme-direction-42')).toContainText('NEGATIVE')

    await page.getByTestId('theme-row-41').click()
    await expect(page).toHaveURL(/\/themes\/41$/)
    await expect(page.getByTestId('theme-detail')).toBeVisible()
    await expect(page.getByTestId('theme-mapping-51')).toContainText('삼성전자')
    await expect(page.getByTestId('theme-detail-signal-71')).toContainText(
      'SUPPLY_SHORTAGE',
    )
    await expect(page.getByText(/source_file_path/)).toHaveCount(0)

    // StockDetail RelatedThemesCard → theme link → /themes/:theme_id
    await page.goto('/stocks/005930')
    await page.getByTestId('stock-detail-theme-link-41').click()
    await expect(page).toHaveURL(/\/themes\/41$/)
    await expect(page.getByTestId('theme-detail')).toBeVisible()
  })

  test('Recommendations table surfaces news / disclosure evidence cells', async ({
    page,
  }) => {
    await page.goto('/recommendations')
    await expect(page.getByTestId('rec-news-evidence-005930')).toBeVisible()
    await expect(page.getByTestId('rec-disclosure-evidence-005930')).toBeVisible()
    // The default fixture (TODAY.top_recommendations) wires neither news_evidence
    // nor disclosure_risk_evidence so both cells render the dash placeholder.
    await expect(page.getByTestId('rec-news-evidence-005930')).toContainText('—')
    await expect(page.getByTestId('rec-disclosure-evidence-005930')).toContainText(
      '—',
    )
    // v0.6 Phase D — fundamental + earnings evidence cells exist (default
    // fixture has no producer wired, so both render "—").
    await expect(page.getByTestId('rec-fund-evidence-005930')).toBeVisible()
    await expect(page.getByTestId('rec-fund-evidence-005930')).toContainText('—')
    await expect(page.getByTestId('rec-earnings-evidence-005930')).toBeVisible()
    await expect(page.getByTestId('rec-earnings-evidence-005930')).toContainText('—')
  })

  test('StockDetail surfaces v0.6 Fundamentals + Earnings cards (read-only)', async ({
    page,
  }) => {
    await page.goto('/stocks/005930')
    await expect(page.getByTestId('stock-detail-fundamentals')).toBeVisible()
    await expect(page.getByTestId('stock-detail-fundamentals-latest')).toBeVisible()
    await expect(page.getByTestId('stock-detail-earnings')).toBeVisible()
    await expect(page.getByTestId('earnings-surprise-BEAT').first()).toBeVisible()
    // Forbidden / source_file_path 0건 노출 — page text + raw payload
    await expect(page.getByText(/source_file_path/)).toHaveCount(0)
    await expect(page.getByText(/원문/)).toHaveCount(0)
    await expect(page.getByText(/본문/)).toHaveCount(0)
    const payload = await page.evaluate(async () => {
      const fund = await fetch('/api/stocks/005930/fundamentals').then(r => r.json())
      const earn = await fetch('/api/stocks/005930/earnings').then(r => r.json())
      return { fund, earn }
    })
    const merged = JSON.stringify(payload)
    expect(merged).not.toContain('source_file_path')
    expect(merged).not.toContain('본문')
    expect(merged).not.toContain('원문')
  })

  test('Today shows the upcoming earnings calendar card with mocked rows', async ({
    page,
  }) => {
    await page.goto('/today')
    await expect(page.getByTestId('today-upcoming-earnings')).toBeVisible()
    await expect(
      page.getByTestId('today-upcoming-earnings-005930'),
    ).toBeVisible()
    await expect(
      page.getByTestId('today-upcoming-earnings-000660'),
    ).toBeVisible()
  })

  test('Backtest screen surfaces strategies + runs + detail (read-only)', async ({
    page,
  }) => {
    await page.goto('/backtest')
    // strategies (3 from mocked /api/strategies)
    await expect(
      page.getByTestId('backtest-strategy-TopGradeStrategy'),
    ).toBeVisible()
    await expect(
      page.getByTestId('backtest-strategy-HighScoreStrategy'),
    ).toBeVisible()
    await expect(
      page.getByTestId('backtest-strategy-MultiSignalStrategy'),
    ).toBeVisible()
    // runs table
    await expect(page.getByTestId('backtest-runs-table')).toBeVisible()
    await expect(page.getByTestId('backtest-run-row-42')).toBeVisible()
    // click → detail loads from /api/backtest/runs/42
    await page.getByTestId('backtest-run-row-42').click()
    await expect(page.getByTestId('backtest-detail')).toBeVisible()
    await expect(page.getByTestId('backtest-detail-cost-model')).toContainText(
      'constant-v1',
    )
    await expect(
      page.getByTestId('backtest-regime-UPTREND_EARLY'),
    ).toBeVisible()
    await expect(page.getByTestId('backtest-result-1001')).toBeVisible()
    await expect(page.getByTestId('backtest-detail-notes')).toContainText(
      'BUY signals only',
    )
    // forbidden tokens absent
    await expect(page.getByText(/source_file_path/)).toHaveCount(0)
    await expect(page.getByText(/원문/)).toHaveCount(0)
    await expect(page.getByText(/본문/)).toHaveCount(0)
    // raw API payload guard
    const payload = await page.evaluate(async () => {
      const list = await fetch('/api/backtest/runs').then(r => r.json())
      const detail = await fetch('/api/backtest/runs/42').then(r => r.json())
      return { list, detail }
    })
    const merged = JSON.stringify(payload)
    expect(merged).not.toContain('source_file_path')
    expect(merged).not.toContain('order_type')
    expect(merged).not.toContain('quantity')
  })

  // -------- v0.8 Phase D --------

  test('Login page auto-redirects to /today when auth_enabled=false', async ({
    page,
  }) => {
    await page.goto('/login')
    // auth_enabled=false (dev_fallback) → immediate redirect to /today
    await expect(
      page.getByRole('heading', { name: '오늘의 리포트', level: 2 }),
    ).toBeVisible()
    expect(page.url()).toContain('/today')
    await expect(page.getByTestId('login-form')).toHaveCount(0)
  })

  test('Watchlist page shows empty state and create form when no watchlists exist', async ({
    page,
  }) => {
    await page.goto('/watchlist')
    await expect(page.getByTestId('watchlist-page')).toBeVisible()
    await expect(page.getByTestId('watchlist-list')).toBeVisible()
    await expect(page.getByTestId('watchlist-list-empty')).toBeVisible()
    await expect(page.getByTestId('watchlist-create-form')).toBeVisible()
    // No trading action buttons or forbidden field labels rendered
    const cta = [/주문\s*(실행|전송|보내기)/, /매수\s*(주문|실행)/, /매도\s*(주문|실행)/]
    for (const pattern of cta) {
      await expect(
        page.locator('button, [role="button"]').filter({ hasText: pattern }),
      ).toHaveCount(0)
    }
    await expect(page.getByText(/broker_name:/)).toHaveCount(0)
    await expect(page.getByText(/order_type/)).toHaveCount(0)
  })

  test('Today page renders WatchlistCard (empty by default)', async ({
    page,
  }) => {
    await page.goto('/today')
    await expect(page.getByTestId('today-watchlist')).toBeVisible()
    // default fixture returns empty watchlists → empty placeholder
    await expect(page.getByTestId('today-watchlist-empty')).toBeVisible()
    // manage link points to /watchlist
    const manageLink = page.getByTestId('today-watchlist').getByRole('link', { name: '관리 →' })
    await expect(manageLink).toHaveAttribute('href', '/watchlist')
  })

  test('StockDetail shows FavoriteButton (inactive, no watchlist)', async ({
    page,
  }) => {
    await page.goto('/stocks/005930')
    await expect(page.getByTestId('favorite-toggle')).toBeVisible()
    await expect(page.getByTestId('favorite-toggle')).toHaveAttribute(
      'data-active',
      'false',
    )
    await expect(page.getByTestId('favorite-toggle')).toHaveAttribute(
      'aria-pressed',
      'false',
    )
  })

  test('Watchlist page never exposes order / trading fields', async ({
    page,
  }) => {
    await page.goto('/watchlist')
    await expect(page.getByTestId('watchlist-page')).toBeVisible()
    await expect(page.getByText(/access_token/)).toHaveCount(0)
    await expect(page.getByText(/password/)).toHaveCount(0)
    await expect(page.getByText(/order_type/)).toHaveCount(0)
    await expect(page.getByText(/order_price/)).toHaveCount(0)
    await expect(page.getByText(/quantity/i)).toHaveCount(0)
    await expect(page.getByText(/source_file_path/)).toHaveCount(0)
  })

  // -------- v0.14 Phase E — Paper / Simulation Trading --------

  test('Paper Trading page surfaces account / positions / pnl / orders and never leaks KIS fields', async ({
    page,
  }) => {
    await page.goto('/paper')
    await expect(page.getByTestId('paper-page')).toBeVisible()
    // Always-on policy banner.
    await expect(page.getByTestId('paper-policy-banner')).toBeVisible()
    // Mocked account fixture renders the totals.
    await expect(page.getByTestId('paper-account-card')).toBeVisible()
    await expect(page.getByTestId('paper-account-cash')).toContainText('9,899,935')
    await expect(page.getByTestId('paper-account-total')).toContainText('10,009,935')
    // Positions / PnL / orders tables all populated by the fixture.
    await expect(page.getByTestId('paper-positions-table')).toBeVisible()
    await expect(page.getByTestId('paper-position-row-005930')).toBeVisible()
    await expect(page.getByTestId('paper-pnl-table')).toBeVisible()
    await expect(page.getByTestId('paper-pnl-row-2026-05-08')).toBeVisible()
    await expect(page.getByTestId('paper-orders-table')).toBeVisible()
    await expect(page.getByTestId('paper-order-row-101')).toBeVisible()
    await expect(page.getByTestId('paper-order-row-102')).toBeVisible()

    // Forbidden DOM tokens — must NOT appear anywhere on the page.
    for (const forbidden of [
      'api_key',
      'access_token',
      'jwt_secret',
      'kis_app_secret',
      'kis_account_no',
      'source_file_path',
      'broker_order_id',
      'kis_order_id',
      'real_account',
      'account_number',
      'raw_text',
      'full_text',
      'broker_name',
    ]) {
      await expect(page.getByText(forbidden)).toHaveCount(0)
    }

    // Automation / autotrade copy must NOT appear in any actionable element.
    for (const phrase of [
      /자동매매\s*(시작|모드|활성)/,
      /실거래\s*(시작|실행|모드)/,
      /FULL_AUTO/,
      /SMALL_AUTO/,
      /APPROVAL/i,
      /place\s*real\s*order/i,
    ]) {
      await expect(
        page.locator('button, [role="button"], a').filter({ hasText: phrase }),
      ).toHaveCount(0)
    }

    // Submit button label is the safe paper-only wording.
    await expect(page.getByTestId('paper-order-submit')).toHaveText(
      /페이퍼 주문 만들기/,
    )

    // Disabled banner appears once a 503 mutation attempt happens (e2e
    // fixture answers POST /api/paper/orders with 503 by default).
    await page.getByTestId('paper-order-symbol-input').fill('005930')
    await page.getByTestId('paper-order-quantity-input').fill('10')
    await page.getByTestId('paper-order-submit').click()
    await expect(page.getByTestId('paper-order-disabled-banner')).toBeVisible()

    // Raw API payload guard.
    const payload = await page.evaluate(async () => {
      const account = await fetch('/api/paper/account').then(r => r.json())
      const orders = await fetch('/api/paper/orders').then(r => r.json())
      const positions = await fetch('/api/paper/positions').then(r => r.json())
      const pnl = await fetch('/api/paper/pnl').then(r => r.json())
      return { account, orders, positions, pnl }
    })
    const merged = JSON.stringify(payload)
    for (const forbidden of [
      'api_key',
      'access_token',
      'jwt_secret',
      'kis_app_secret',
      'broker_order_id',
      'kis_order_id',
      'real_account',
      'account_number',
      'source_file_path',
      'raw_text',
      'full_text',
    ]) {
      expect(merged).not.toContain(forbidden)
    }
  })

  // -------- v0.15 Phase E — Approval Workflow --------

  test('Approvals page surfaces policy banner / pending table / new-candidate form, never leaks KIS fields', async ({
    page,
  }) => {
    await page.goto('/approvals')
    await expect(page.getByTestId('approvals-page')).toBeVisible()
    await expect(page.getByTestId('approvals-policy-banner')).toBeVisible()
    // GET /api/approvals/candidates returns empty in the e2e fixture →
    // empty placeholder is the expected state.
    await expect(page.getByTestId('approvals-pending-empty')).toBeVisible()
    await expect(page.getByTestId('approvals-history-empty')).toBeVisible()
    await expect(page.getByTestId('approvals-new-form')).toBeVisible()

    // Submit button label is the safe approval wording.
    await expect(page.getByTestId('approvals-new-submit')).toHaveText(
      /후보 만들기 \(Risk Check\)/,
    )

    // Forbidden DOM tokens — must NOT appear anywhere on the page.
    for (const forbidden of [
      'api_key',
      'access_token',
      'jwt_secret',
      'kis_app_secret',
      'kis_account_no',
      'source_file_path',
      'broker_order_id',
      'kis_order_id',
      'real_account',
      'real_order_id',
      'account_number',
      'raw_text',
      'full_text',
    ]) {
      await expect(page.getByText(forbidden)).toHaveCount(0)
    }

    // Automation / autotrade copy must NOT appear in any actionable element.
    for (const phrase of [
      /자동매매\s*(시작|모드|활성)/,
      /실거래\s*(시작|실행|모드)/,
      /FULL_AUTO/,
      /SMALL_AUTO/,
      /place\s*real\s*order/i,
      /실\s*KIS\s*(주문|실행)/,
    ]) {
      await expect(
        page.locator('button, [role="button"], a').filter({ hasText: phrase }),
      ).toHaveCount(0)
    }

    // 503 banner appears once a submit attempt happens (e2e fixture answers
    // POST /api/approvals/candidates with 503).
    await page.getByTestId('approvals-new-symbol-input').fill('005930')
    await page.getByTestId('approvals-new-quantity-input').fill('10')
    await page.getByTestId('approvals-new-submit').click()
    await expect(page.getByTestId('approvals-new-disabled-banner')).toBeVisible()

    // Raw API payload guard.
    const payload = await page.evaluate(async () => {
      const candidates = await fetch('/api/approvals/candidates').then(r => r.json())
      const audit = await fetch('/api/approvals/audit').then(r => r.json())
      return { candidates, audit }
    })
    const merged = JSON.stringify(payload)
    for (const forbidden of [
      'api_key',
      'access_token',
      'jwt_secret',
      'kis_app_secret',
      'broker_order_id',
      'kis_order_id',
      'real_account',
      'real_order_id',
      'account_number',
      'source_file_path',
      'raw_text',
      'full_text',
    ]) {
      expect(merged).not.toContain(forbidden)
    }
  })

  // -------- v0.16 Phase E — Real Orders read-only --------

  test('Real Orders page shows safety banner and empty state, never leaks KIS fields', async ({
    page,
  }) => {
    await page.goto('/real-orders')
    await expect(page.getByTestId('real-orders-page')).toBeVisible()
    await expect(page.getByTestId('real-orders-safety-banner')).toBeVisible()
    // Default e2e fixture returns empty → empty placeholder
    await expect(page.getByTestId('real-orders-empty')).toBeVisible()

    // Forbidden DOM tokens must NOT appear anywhere on the page.
    for (const forbidden of [
      'api_key',
      'access_token',
      'jwt_secret',
      'kis_app_secret',
      'kis_account_no',
      'broker_order_no_hash',
      'raw_response',
      'source_file_path',
      'real_account',
      'account_number',
      'raw_text',
      'full_text',
    ]) {
      await expect(page.getByText(forbidden)).toHaveCount(0)
    }

    // Automation / autotrade copy must NOT appear in any actionable element.
    for (const phrase of [
      /자동매매\s*(시작|모드|활성)/,
      /실거래\s*(시작|실행|모드)/,
      /FULL_AUTO/,
      /SMALL_AUTO/,
      /place\s*real\s*order/i,
      /실주문\s*실행/,
      /주문\s*전송/,
    ]) {
      await expect(
        page.locator('button, [role="button"], a').filter({ hasText: phrase }),
      ).toHaveCount(0)
    }

    // Raw API payload guard.
    const payload = await page.evaluate(async () => {
      const orders = await fetch('/api/real-orders').then(r => r.json())
      return { orders }
    })
    const merged = JSON.stringify(payload)
    for (const forbidden of [
      'api_key',
      'access_token',
      'broker_order_no_hash',
      'raw_response',
      'real_account',
      'account_number',
      'raw_text',
    ]) {
      expect(merged).not.toContain(forbidden)
    }
  })

  test('no automation / order UI is exposed anywhere in v0.2 frontend', async ({
    page,
  }) => {
    const targets = [
      '/today',
      '/recommendations',
      '/recommendations/history',
      '/holdings',
      '/holdings/005930',
      '/stocks/005930',
      '/universe/market-cap-top',
      '/themes',
      '/themes/41',
      '/backtest',
      '/validation',
      '/jobs',
      '/jobs/101',
      '/settings',
    ]
    for (const path of targets) {
      await page.goto(path)
      await expect(page.getByTestId('page-loading')).toHaveCount(0, {
        timeout: 5000,
      })

      // (a) form submit 트리거가 일체 노출되면 안 된다 (v0.2 frontend 는 read-only)
      const submitButtons = await page.locator('button[type="submit"]').count()
      expect(submitButtons, `path=${path} has submit button(s)`).toBe(0)
      const forms = await page.locator('form').count()
      expect(forms, `path=${path} has form element(s)`).toBe(0)

      // (b) "실거래 시작" / "자동매매 시작" / "주문 실행" 같은 actionable CTA
      // 라벨이 button / link 에 들어있지 않아야 한다. Sidebar 의 안전 문구
      // ("자동매매 / 실 주문 미포함") 같은 read-only 설명은 버튼이 아니라
      // <p>·<span> 이라 selector 자체가 잡지 않는다.
      const cta = [
        /실거래\s*(시작|실행|모드)/,
        /자동매매\s*(시작|모드|활성)/,
        /주문\s*(실행|전송|보내기)/,
        /place\s*order/i,
        /submit\s*order/i,
        /enable\s*real\s*trading/i,
      ]
      for (const pattern of cta) {
        const matchingButtons = await page
          .locator('button, [role="button"], a')
          .filter({ hasText: pattern })
          .count()
        expect(
          matchingButtons,
          `path=${path} has actionable CTA matching ${pattern}`,
        ).toBe(0)
      }
    }
  })
})
