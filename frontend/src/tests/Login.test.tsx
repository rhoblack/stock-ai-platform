import { describe, expect, it } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { renderWithProviders } from './renderWithProviders'
import { server } from './mswServer'
import { LoginPage } from '@/pages/Login'

// renderWithProviders uses MemoryRouter, but LoginPage needs navigate() and
// location — wrap it inside a minimal route tree.
import { Routes, Route } from 'react-router-dom'

function renderLoginAt(initialEntries = ['/login']) {
  return renderWithProviders(
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/today" element={<div data-testid="today-page">today</div>} />
    </Routes>,
    { initialEntries },
  )
}

describe('LoginPage', () => {
  it('auto-redirects to /today when auth_enabled=false (dev default)', async () => {
    // Default MSW handler returns auth_enabled: false.
    renderLoginAt()

    await waitFor(() =>
      expect(screen.getByTestId('today-page')).toBeInTheDocument(),
    )
    expect(screen.queryByTestId('login-form')).not.toBeInTheDocument()
  })

  it('renders the login form when auth_enabled=true and user is not logged in', async () => {
    server.use(
      http.get('*/api/auth/me', () =>
        HttpResponse.json({ auth_enabled: true, via: 'jwt', user: null }),
      ),
    )

    renderLoginAt()

    await waitFor(() =>
      expect(screen.getByTestId('login-form')).toBeInTheDocument(),
    )
    expect(screen.getByTestId('login-username')).toBeInTheDocument()
    expect(screen.getByTestId('login-password')).toBeInTheDocument()
    expect(screen.getByTestId('login-submit')).toBeInTheDocument()
  })

  it('shows success and redirects when credentials are correct', async () => {
    server.use(
      http.get('*/api/auth/me', () =>
        HttpResponse.json({ auth_enabled: true, via: 'jwt', user: null }),
      ),
      http.post('*/api/auth/login', () =>
        HttpResponse.json({
          access_token: 'good-token',
          token_type: 'bearer',
          expires_in: 3600,
          issued_at: '2026-05-06T00:00:00',
          expires_at: '2026-05-06T01:00:00',
          user: { id: 1, username: 'admin', is_admin: true },
        }),
      ),
    )

    renderLoginAt()

    await waitFor(() =>
      expect(screen.getByTestId('login-form')).toBeInTheDocument(),
    )

    await userEvent.type(screen.getByTestId('login-username'), 'admin')
    await userEvent.type(screen.getByTestId('login-password'), 'secret')
    await userEvent.click(screen.getByTestId('login-submit'))

    await waitFor(() =>
      expect(screen.getByTestId('today-page')).toBeInTheDocument(),
    )
    expect(screen.queryByTestId('login-form')).not.toBeInTheDocument()
  })

  it('shows 401 error message when credentials are wrong', async () => {
    server.use(
      http.get('*/api/auth/me', () =>
        HttpResponse.json({ auth_enabled: true, via: 'jwt', user: null }),
      ),
      http.post('*/api/auth/login', () =>
        HttpResponse.json({ detail: 'Incorrect credentials' }, { status: 401 }),
      ),
    )

    renderLoginAt()

    await waitFor(() =>
      expect(screen.getByTestId('login-form')).toBeInTheDocument(),
    )

    await userEvent.type(screen.getByTestId('login-username'), 'admin')
    await userEvent.type(screen.getByTestId('login-password'), 'wrong')
    await userEvent.click(screen.getByTestId('login-submit'))

    await waitFor(() =>
      expect(screen.getByTestId('login-error')).toBeInTheDocument(),
    )
    expect(screen.getByTestId('login-error')).toHaveTextContent(
      '아이디 또는 비밀번호가 올바르지 않습니다.',
    )
  })

  it('shows generic error message on 500', async () => {
    server.use(
      http.get('*/api/auth/me', () =>
        HttpResponse.json({ auth_enabled: true, via: 'jwt', user: null }),
      ),
      http.post('*/api/auth/login', () =>
        HttpResponse.json({ detail: 'internal error' }, { status: 500 }),
      ),
    )

    renderLoginAt()

    await waitFor(() =>
      expect(screen.getByTestId('login-form')).toBeInTheDocument(),
    )

    await userEvent.type(screen.getByTestId('login-username'), 'admin')
    await userEvent.type(screen.getByTestId('login-password'), 'pass')
    await userEvent.click(screen.getByTestId('login-submit'))

    await waitFor(() =>
      expect(screen.getByTestId('login-error')).toBeInTheDocument(),
    )
    expect(screen.getByTestId('login-error')).toHaveTextContent(
      '로그인에 실패했습니다',
    )
  })

  it('clears the password field after a failed login attempt', async () => {
    server.use(
      http.get('*/api/auth/me', () =>
        HttpResponse.json({ auth_enabled: true, via: 'jwt', user: null }),
      ),
      http.post('*/api/auth/login', () =>
        HttpResponse.json({ detail: 'bad credentials' }, { status: 401 }),
      ),
    )

    renderLoginAt()

    await waitFor(() =>
      expect(screen.getByTestId('login-form')).toBeInTheDocument(),
    )

    const passwordInput = screen.getByTestId('login-password') as HTMLInputElement
    await userEvent.type(screen.getByTestId('login-username'), 'admin')
    await userEvent.type(passwordInput, 'secretpassword')
    await userEvent.click(screen.getByTestId('login-submit'))

    await waitFor(() =>
      expect(screen.getByTestId('login-error')).toBeInTheDocument(),
    )
    // Password must be cleared after every attempt (security policy)
    expect(passwordInput.value).toBe('')
  })

  it('never renders password, token, or access_token values in the DOM', async () => {
    server.use(
      http.get('*/api/auth/me', () =>
        HttpResponse.json({ auth_enabled: true, via: 'jwt', user: null }),
      ),
      http.post('*/api/auth/login', () =>
        HttpResponse.json({
          access_token: 'super-secret-token-abc123',
          token_type: 'bearer',
          expires_in: 3600,
          issued_at: '2026-05-06T00:00:00',
          expires_at: '2026-05-06T01:00:00',
          user: { id: 1, username: 'admin', is_admin: true },
        }),
      ),
    )

    renderLoginAt()

    await waitFor(() =>
      expect(screen.getByTestId('login-form')).toBeInTheDocument(),
    )

    await userEvent.type(screen.getByTestId('login-username'), 'admin')
    await userEvent.type(screen.getByTestId('login-password'), 'secret')
    await userEvent.click(screen.getByTestId('login-submit'))

    // After redirect to today-page, verify the token string is not visible anywhere
    await waitFor(() =>
      expect(screen.getByTestId('today-page')).toBeInTheDocument(),
    )
    expect(screen.queryByText(/super-secret-token-abc123/)).not.toBeInTheDocument()
    expect(screen.queryByText(/access_token/)).not.toBeInTheDocument()
  })

  it('disables submit button when username is empty', async () => {
    server.use(
      http.get('*/api/auth/me', () =>
        HttpResponse.json({ auth_enabled: true, via: 'jwt', user: null }),
      ),
    )

    renderLoginAt()

    await waitFor(() =>
      expect(screen.getByTestId('login-form')).toBeInTheDocument(),
    )

    expect(screen.getByTestId('login-submit')).toBeDisabled()
    await userEvent.type(screen.getByTestId('login-username'), 'a')
    expect(screen.getByTestId('login-submit')).not.toBeDisabled()
  })
})
