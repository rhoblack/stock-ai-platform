// v0.10 Phase D — ProviderHealthPanel tests.
//
// Verifies:
//  * happy path renders 3 default rows (kis / dart / rss) with badges
//  * disabled / not_configured states render correct badge text
//  * OPEN circuit state renders red badge
//  * last_error_kind is shown when present
//  * 500 response renders the error placeholder, not raw error text
//  * forbidden secrets are NEVER rendered into the DOM (whitelist guard)
//  * empty items array renders the empty placeholder

import { describe, expect, it } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { renderWithProviders } from './renderWithProviders'
import { server } from './mswServer'
import { ProviderHealthPanel } from '@/components/common/ProviderHealthPanel'

describe('ProviderHealthPanel', () => {
  it('renders the three canonical providers when nothing is enabled', async () => {
    renderWithProviders(<ProviderHealthPanel />)
    await waitFor(() =>
      expect(screen.getByTestId('provider-health-table')).toBeInTheDocument(),
    )
    expect(screen.getByTestId('provider-row-kis')).toBeInTheDocument()
    expect(screen.getByTestId('provider-row-dart')).toBeInTheDocument()
    expect(screen.getByTestId('provider-row-rss')).toBeInTheDocument()
  })

  it('renders disabled/not_configured badges for default-OFF providers', async () => {
    renderWithProviders(<ProviderHealthPanel />)
    await waitFor(() =>
      expect(screen.getByTestId('provider-row-dart')).toBeInTheDocument(),
    )
    expect(screen.getByTestId('provider-enabled-dart')).toHaveTextContent(
      'disabled',
    )
    expect(screen.getByTestId('provider-configured-dart')).toHaveTextContent(
      'not_configured',
    )
    expect(screen.getByTestId('provider-state-dart')).toHaveTextContent(
      'UNREGISTERED',
    )
    expect(screen.getByTestId('provider-row-dart')).toHaveAttribute(
      'data-enabled',
      'false',
    )
    expect(screen.getByTestId('provider-row-dart')).toHaveAttribute(
      'data-configured',
      'false',
    )
  })

  it('renders OPEN circuit state with red badge data-state', async () => {
    server.use(
      http.get('*/api/health/providers', () =>
        HttpResponse.json({
          items: [
            {
              provider_name: 'kis',
              enabled: true,
              configured: true,
              circuit_state: 'CLOSED',
              call_count: 10,
              success_count: 10,
              failure_count: 0,
              last_error_kind: null,
              last_called_at: '2026-05-07T08:00:00Z',
            },
            {
              provider_name: 'dart',
              enabled: true,
              configured: true,
              circuit_state: 'OPEN',
              call_count: 5,
              success_count: 0,
              failure_count: 5,
              last_error_kind: 'TIMEOUT',
              last_called_at: '2026-05-07T08:01:00Z',
            },
            {
              provider_name: 'rss',
              enabled: false,
              configured: false,
              circuit_state: 'UNREGISTERED',
              call_count: 0,
              success_count: 0,
              failure_count: 0,
              last_error_kind: null,
              last_called_at: null,
            },
          ],
          count: 3,
        }),
      ),
    )
    renderWithProviders(<ProviderHealthPanel />)
    await waitFor(() =>
      expect(screen.getByTestId('provider-row-dart')).toHaveAttribute(
        'data-state',
        'OPEN',
      ),
    )
    expect(screen.getByTestId('provider-state-dart')).toHaveTextContent('OPEN')
    expect(screen.getByTestId('provider-last-error-dart')).toHaveTextContent(
      'TIMEOUT',
    )
    // KIS healthy
    expect(screen.getByTestId('provider-row-kis')).toHaveAttribute(
      'data-state',
      'CLOSED',
    )
  })

  it('renders error placeholder on 500 response', async () => {
    server.use(
      http.get('*/api/health/providers', () =>
        HttpResponse.json({ detail: 'boom' }, { status: 500 }),
      ),
    )
    renderWithProviders(<ProviderHealthPanel />)
    await waitFor(() =>
      expect(screen.getByTestId('provider-health-error')).toBeInTheDocument(),
    )
    // No raw 500 / "Error" message bleeds through.
    expect(screen.queryByText(/boom/)).not.toBeInTheDocument()
    // Table not rendered when error.
    expect(screen.queryByTestId('provider-health-table')).not.toBeInTheDocument()
  })

  it('renders empty placeholder when items array is empty', async () => {
    server.use(
      http.get('*/api/health/providers', () =>
        HttpResponse.json({ items: [], count: 0 }),
      ),
    )
    renderWithProviders(<ProviderHealthPanel />)
    await waitFor(() =>
      expect(screen.getByTestId('provider-health-empty')).toBeInTheDocument(),
    )
  })

  it('never renders secret-bearing field names or values into the DOM', async () => {
    // Even if (hypothetically) the backend leaked secrets, the panel
    // only references whitelisted fields -- this test belt-and-suspenders
    // verifies the rendered text.
    server.use(
      http.get('*/api/health/providers', () =>
        HttpResponse.json({
          items: [
            {
              provider_name: 'dart',
              enabled: true,
              configured: true,
              circuit_state: 'CLOSED',
              call_count: 1,
              success_count: 1,
              failure_count: 0,
              last_error_kind: null,
              last_called_at: '2026-05-07T08:00:00Z',
              // Unknown extra fields the panel must NOT surface even if
              // the backend sent them by mistake.
              dart_api_key: 'SHOULD-NEVER-RENDER',
              crtfc_key: 'ALSO-NEVER',
              feed_url: 'https://example.com?api_key=LEAK',
            } as unknown as never,
          ],
          count: 1,
        }),
      ),
    )
    const { container } = renderWithProviders(<ProviderHealthPanel />)
    await waitFor(() =>
      expect(screen.getByTestId('provider-row-dart')).toBeInTheDocument(),
    )
    const text = container.textContent ?? ''
    for (const forbidden of [
      'SHOULD-NEVER-RENDER',
      'ALSO-NEVER',
      'LEAK',
      'crtfc_key',
      'dart_api_key',
      'api_key',
      'access_token',
      'password',
    ]) {
      expect(text).not.toContain(forbidden)
    }
  })

  it('does not render enable/disable toggle controls', async () => {
    renderWithProviders(<ProviderHealthPanel />)
    await waitFor(() =>
      expect(screen.getByTestId('provider-health-table')).toBeInTheDocument(),
    )
    // Read-only -- no buttons, no submit, no form.
    expect(screen.queryAllByRole('button')).toHaveLength(0)
    expect(screen.queryByRole('checkbox')).not.toBeInTheDocument()
    expect(screen.queryByRole('switch')).not.toBeInTheDocument()
  })

  // ------------------------------------------------------------------
  // v0.11 Phase D — success_rate_24h / avg_attempts_24h / recent_failures
  // ------------------------------------------------------------------

  it('renders success_rate_24h percentage and avg_attempts cells (Phase D)', async () => {
    server.use(
      http.get('*/api/health/providers', () =>
        HttpResponse.json({
          items: [
            {
              provider_name: 'kis',
              enabled: true,
              configured: true,
              circuit_state: 'CLOSED',
              call_count: 100,
              success_count: 99,
              failure_count: 1,
              last_error_kind: 'TIMEOUT',
              last_called_at: '2026-05-07T12:00:00Z',
              call_count_24h: 100,
              success_count_24h: 99,
              failure_count_24h: 1,
              success_rate_24h: 0.99,
              avg_attempts_24h: 1.07,
              recent_failures: [],
            },
            {
              provider_name: 'dart',
              enabled: false,
              configured: false,
              circuit_state: 'UNREGISTERED',
              call_count: 0,
              success_count: 0,
              failure_count: 0,
              last_error_kind: null,
              last_called_at: null,
              call_count_24h: 0,
              success_count_24h: 0,
              failure_count_24h: 0,
              success_rate_24h: null,
              avg_attempts_24h: null,
              recent_failures: [],
            },
            {
              provider_name: 'rss',
              enabled: false,
              configured: false,
              circuit_state: 'UNREGISTERED',
              call_count: 0,
              success_count: 0,
              failure_count: 0,
              last_error_kind: null,
              last_called_at: null,
              call_count_24h: 0,
              success_count_24h: 0,
              failure_count_24h: 0,
              success_rate_24h: null,
              avg_attempts_24h: null,
              recent_failures: [],
            },
          ],
          count: 3,
        }),
      ),
    )
    renderWithProviders(<ProviderHealthPanel />)

    await waitFor(() =>
      expect(screen.getByTestId('provider-success-rate-kis')).toBeInTheDocument(),
    )
    expect(screen.getByTestId('provider-success-rate-kis')).toHaveTextContent(
      '99.0%',
    )
    expect(
      screen.getByTestId('provider-success-rate-kis'),
    ).toHaveAttribute('data-rate', '0.99')
    expect(screen.getByTestId('provider-avg-attempts-kis')).toHaveTextContent(
      '1.07',
    )
    // Empty / unregistered providers show the dash placeholder.
    expect(screen.getByTestId('provider-success-rate-dart')).toHaveTextContent(
      '—',
    )
    expect(screen.getByTestId('provider-avg-attempts-dart')).toHaveTextContent(
      '—',
    )
  })

  it('renders the recent failures list with newest first (Phase D)', async () => {
    server.use(
      http.get('*/api/health/providers', () =>
        HttpResponse.json({
          items: [
            {
              provider_name: 'dart',
              enabled: true,
              configured: true,
              circuit_state: 'OPEN',
              call_count: 12,
              success_count: 4,
              failure_count: 8,
              last_error_kind: 'SERVER_ERROR',
              last_called_at: '2026-05-07T12:30:00Z',
              call_count_24h: 12,
              success_count_24h: 4,
              failure_count_24h: 8,
              success_rate_24h: 0.33,
              avg_attempts_24h: 2.4,
              recent_failures: [
                { timestamp: '2026-05-07T12:30:00Z', error_kind: 'SERVER_ERROR' },
                { timestamp: '2026-05-07T12:20:00Z', error_kind: 'TIMEOUT' },
                { timestamp: '2026-05-07T12:10:00Z', error_kind: 'CLIENT_ERROR' },
              ],
            },
            {
              provider_name: 'kis',
              enabled: true,
              configured: true,
              circuit_state: 'CLOSED',
              call_count: 50,
              success_count: 50,
              failure_count: 0,
              last_error_kind: null,
              last_called_at: '2026-05-07T12:00:00Z',
              call_count_24h: 50,
              success_count_24h: 50,
              failure_count_24h: 0,
              success_rate_24h: 1.0,
              avg_attempts_24h: 1.0,
              recent_failures: [],
            },
            {
              provider_name: 'rss',
              enabled: false,
              configured: false,
              circuit_state: 'UNREGISTERED',
              call_count: 0,
              success_count: 0,
              failure_count: 0,
              last_error_kind: null,
              last_called_at: null,
              call_count_24h: 0,
              success_count_24h: 0,
              failure_count_24h: 0,
              success_rate_24h: null,
              avg_attempts_24h: null,
              recent_failures: [],
            },
          ],
          count: 3,
        }),
      ),
    )
    renderWithProviders(<ProviderHealthPanel />)

    await waitFor(() =>
      expect(
        screen.getByTestId('provider-recent-failures-section'),
      ).toBeInTheDocument(),
    )
    // Only DART rendered in the failures section (KIS = 0 failures, RSS unregistered).
    expect(
      screen.getByTestId('provider-recent-failures-card-dart'),
    ).toBeInTheDocument()
    expect(
      screen.queryByTestId('provider-recent-failures-card-kis'),
    ).not.toBeInTheDocument()
    expect(
      screen.queryByTestId('provider-recent-failures-card-rss'),
    ).not.toBeInTheDocument()

    // Three failure rows for DART.
    const list = screen.getByTestId('provider-recent-failures-dart')
    expect(list.children).toHaveLength(3)
    // First entry is the newest by error_kind (SERVER_ERROR @ 12:30).
    expect(
      screen.getByTestId('provider-recent-failure-dart-0'),
    ).toHaveTextContent('SERVER_ERROR')
    expect(
      screen.getByTestId('provider-recent-failure-dart-1'),
    ).toHaveTextContent('TIMEOUT')
    expect(
      screen.getByTestId('provider-recent-failure-dart-2'),
    ).toHaveTextContent('CLIENT_ERROR')
  })

  it('shows the empty-failures placeholder when recent_failures is empty (Phase D)', async () => {
    // The default MSW handler returns all-zero providers with empty
    // recent_failures, so the section itself does NOT render.  This
    // test asserts that the section is absent in the all-empty case.
    renderWithProviders(<ProviderHealthPanel />)
    await waitFor(() =>
      expect(screen.getByTestId('provider-health-table')).toBeInTheDocument(),
    )
    expect(
      screen.queryByTestId('provider-recent-failures-section'),
    ).not.toBeInTheDocument()
  })

  it('never renders message text from recent_failures (secret guard)', async () => {
    // Backend schema does not include a `message` field on
    // recent_failures, but we verify the component cannot render one
    // even if a hypothetical backend regression sneaked it in.
    server.use(
      http.get('*/api/health/providers', () =>
        HttpResponse.json({
          items: [
            {
              provider_name: 'dart',
              enabled: true,
              configured: true,
              circuit_state: 'OPEN',
              call_count: 1,
              success_count: 0,
              failure_count: 1,
              last_error_kind: 'TIMEOUT',
              last_called_at: '2026-05-07T12:00:00Z',
              call_count_24h: 1,
              success_count_24h: 0,
              failure_count_24h: 1,
              success_rate_24h: 0.0,
              avg_attempts_24h: 1.0,
              recent_failures: [
                {
                  timestamp: '2026-05-07T12:00:00Z',
                  error_kind: 'TIMEOUT',
                  // Hypothetical leaked field — must not surface anywhere
                  // in the rendered DOM.
                  message:
                    'GET https://opendart.fss.or.kr/api/x?crtfc_key=LEAKMEXYZ',
                } as unknown as never,
              ],
            },
          ],
          count: 1,
        }),
      ),
    )
    const { container } = renderWithProviders(<ProviderHealthPanel />)
    await waitFor(() =>
      expect(
        screen.getByTestId('provider-recent-failure-dart-0'),
      ).toBeInTheDocument(),
    )
    const text = container.textContent ?? ''
    for (const forbidden of [
      'LEAKMEXYZ',
      'crtfc_key',
      'opendart',
      'api_key',
    ]) {
      expect(text).not.toContain(forbidden)
    }
  })

  it('keeps the panel read-only after Phase D additions (no buttons / form / switch)', async () => {
    server.use(
      http.get('*/api/health/providers', () =>
        HttpResponse.json({
          items: [
            {
              provider_name: 'dart',
              enabled: true,
              configured: true,
              circuit_state: 'OPEN',
              call_count: 1,
              success_count: 0,
              failure_count: 1,
              last_error_kind: 'TIMEOUT',
              last_called_at: '2026-05-07T12:00:00Z',
              call_count_24h: 1,
              success_count_24h: 0,
              failure_count_24h: 1,
              success_rate_24h: 0.0,
              avg_attempts_24h: 1.0,
              recent_failures: [
                { timestamp: '2026-05-07T12:00:00Z', error_kind: 'TIMEOUT' },
              ],
            },
          ],
          count: 1,
        }),
      ),
    )
    renderWithProviders(<ProviderHealthPanel />)
    await waitFor(() =>
      expect(
        screen.getByTestId('provider-recent-failures-section'),
      ).toBeInTheDocument(),
    )
    expect(screen.queryAllByRole('button')).toHaveLength(0)
    expect(screen.queryByRole('checkbox')).not.toBeInTheDocument()
    expect(screen.queryByRole('switch')).not.toBeInTheDocument()
    // No input element either — the failures section is pure read-only.
    expect(screen.queryByRole('textbox')).not.toBeInTheDocument()
  })
})
