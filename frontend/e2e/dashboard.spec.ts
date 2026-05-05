import { test, expect } from '@playwright/test'
import { installApiMocks } from './fixtures/apiMocks'

test.beforeEach(async ({ page }) => {
  await installApiMocks(page)
})

test.describe('v0.2 Phase F — dashboard happy paths (8 screens, mocked API)', () => {
  test('all 8 sidebar menus are reachable and render their main content', async ({
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
