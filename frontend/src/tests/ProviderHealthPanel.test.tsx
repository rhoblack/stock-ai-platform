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
})
