import { defineConfig, devices } from '@playwright/test'

// v0.2 Phase F E2E. 백엔드 의존 없이 실행되도록 설계: Playwright 가
// `npm run preview` 로 빌드된 정적 번들을 띄우고, 각 테스트가
// `page.route('**/api/**', ...)` 로 백엔드 응답을 mock 한다.
// 실 KIS / 실 텔레그램 / 실 백엔드 호출 0건. v0.1 mock 경계 그대로 준수.
export default defineConfig({
  testDir: './e2e',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? 'github' : 'list',
  timeout: 30_000,
  use: {
    baseURL: 'http://127.0.0.1:4173',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
  webServer: {
    command: 'npm run preview -- --host 127.0.0.1 --port 4173 --strictPort',
    url: 'http://127.0.0.1:4173',
    reuseExistingServer: !process.env.CI,
    timeout: 60_000,
    stdout: 'pipe',
    stderr: 'pipe',
  },
})
