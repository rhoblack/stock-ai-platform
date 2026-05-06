// v0.8 Phase D — Login screen.
// Displayed outside AppLayout at /login.
// When AUTH_ENABLED=false (dev default) the component auto-redirects to the
// home page — no manual login needed. When AUTH_ENABLED=true the form is
// shown and calls POST /api/auth/login.
//
// Security notes:
//   • password value is never rendered to the DOM or logged.
//   • On every submit attempt (success OR failure) the password state is
//     cleared immediately after the fetch resolves.
//   • The raw access_token from the response is passed to onLoginSuccess()
//     which stores it in localStorage; it is never placed in JSX output.

import { useEffect, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '@/store/auth'
import { login as loginApi } from '@/api/auth'
import { ApiError } from '@/api/client'

export function LoginPage() {
  const { onLoginSuccess, authEnabled, isAuthenticated, isLoading } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()

  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [errorMsg, setErrorMsg] = useState<string | null>(null)
  const [pending, setPending] = useState(false)

  const from = (location.state as { from?: string } | null)?.from ?? '/today'

  useEffect(() => {
    if (!isLoading && (!authEnabled || isAuthenticated)) {
      navigate(from, { replace: true })
    }
  }, [isLoading, authEnabled, isAuthenticated, navigate, from])

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault()
    if (!username.trim() || pending) return
    setPending(true)
    setErrorMsg(null)
    try {
      const resp = await loginApi(username, password)
      onLoginSuccess(resp)
      navigate(from, { replace: true })
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        setErrorMsg('아이디 또는 비밀번호가 올바르지 않습니다.')
      } else {
        setErrorMsg('로그인에 실패했습니다. 잠시 후 다시 시도해 주세요.')
      }
    } finally {
      setPassword('')
      setPending(false)
    }
  }

  if (isLoading) {
    return (
      <div
        data-testid="login-loading"
        className="flex min-h-screen items-center justify-center bg-background"
      >
        <p className="text-sm text-muted-foreground">로딩 중…</p>
      </div>
    )
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-4">
      <div className="w-full max-w-sm rounded-lg border border-border bg-card p-8 shadow-sm">
        {/* Brand */}
        <div className="mb-6 flex flex-col items-center gap-2">
          <div className="flex h-10 w-10 items-center justify-center rounded-md bg-primary text-primary-foreground text-sm font-bold">
            AI
          </div>
          <h1 className="text-xl font-semibold">Stock AI</h1>
          <p className="text-xs text-muted-foreground">분석 대시보드 로그인</p>
        </div>

        <form onSubmit={handleSubmit} noValidate data-testid="login-form">
          {/* Username */}
          <div className="mb-4">
            <label
              htmlFor="login-username"
              className="mb-1 block text-sm font-medium"
            >
              사용자명
            </label>
            <input
              id="login-username"
              data-testid="login-username"
              type="text"
              autoComplete="username"
              required
              value={username}
              onChange={e => setUsername(e.target.value)}
              disabled={pending}
              className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-primary disabled:opacity-50"
            />
          </div>

          {/* Password — value never rendered; cleared after each attempt */}
          <div className="mb-4">
            <label
              htmlFor="login-password"
              className="mb-1 block text-sm font-medium"
            >
              비밀번호
            </label>
            <input
              id="login-password"
              data-testid="login-password"
              type="password"
              autoComplete="current-password"
              required
              value={password}
              onChange={e => setPassword(e.target.value)}
              disabled={pending}
              className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-primary disabled:opacity-50"
            />
          </div>

          {/* Error */}
          {errorMsg && (
            <p
              data-testid="login-error"
              role="alert"
              className="mb-4 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700 dark:border-red-900/40 dark:bg-red-900/20 dark:text-red-300"
            >
              {errorMsg}
            </p>
          )}

          <button
            type="submit"
            data-testid="login-submit"
            disabled={pending || !username.trim()}
            className="w-full rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90 disabled:opacity-50"
          >
            {pending ? '로그인 중…' : '로그인'}
          </button>
        </form>

        <p className="mt-6 text-center text-xs text-muted-foreground">
          Stock AI Platform · read-only 분석 대시보드
        </p>
      </div>
    </div>
  )
}
