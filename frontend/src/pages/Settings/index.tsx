// Settings page (/settings).
// v0.1: read-only backend diagnostics
// v0.9 Phase D: added UserPreference section (writable) above system section.
//
// Policy:
//   - KIS keys / Telegram tokens / JWT secrets are NEVER shown in plain text
//   - notification_preferences_json: UI-only on/off toggles, no live send
//   - Forbidden fields (password, password_hash, access_token, jwt_secret,
//     broker, account, quantity, order_*, source_file_path, side) never rendered

import { useState } from 'react'
import { AlertTriangle, Save } from 'lucide-react'
import { useSettings } from '@/hooks/useSettings'
import { useWatchlists } from '@/hooks/useWatchlists'
import { useUserPreferences, useUpdateUserPreferences } from '@/hooks/useUserPreferences'
import { KeyValueGrid } from '@/components/common/KeyValueGrid'
import { SafetyFlagBadge } from '@/components/common/SafetyFlagBadge'
import { ApiError } from '@/api/client'
import type { SettingsResponse } from '@/api/types'

const MARKET_OPTIONS = ['', 'KOSPI', 'KOSDAQ', 'NASDAQ', 'NYSE']
const STRATEGY_OPTIONS = ['', 'momentum', 'value', 'growth', 'technical']

export function SettingsPage() {
  const settings = useSettings()

  return (
    <section data-testid="settings-page" className="flex flex-col gap-6">
      <header className="flex flex-col gap-1">
        <h2 className="text-2xl font-semibold">설정</h2>
        <p className="text-sm text-muted-foreground">
          사용자 설정 및 백엔드 진단 정보
        </p>
      </header>

      {/* User Preference section (writable) */}
      <UserPreferenceSection />

      <hr className="border-border" />

      {/* System settings (read-only) */}
      <div
        data-testid="settings-freeze-banner"
        className="flex items-start gap-3 rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm dark:border-amber-900/40 dark:bg-amber-900/20"
      >
        <AlertTriangle
          className="mt-0.5 h-4 w-4 text-amber-600 dark:text-amber-300"
          aria-hidden
        />
        <div className="flex flex-col gap-1">
          <strong className="font-semibold text-amber-900 dark:text-amber-100">
            v0.1 백엔드 동결 (`v0.1-backend-final`)
          </strong>
          <span className="text-xs text-amber-800 dark:text-amber-200">
            아래 값은 백엔드 응답을 그대로 보여주는 read-only 진단 정보입니다.
            변경은 <code>.env</code> 수정 후 백엔드 재시작으로만 가능합니다.
          </span>
        </div>
      </div>

      {settings.isLoading && (
        <div className="rounded-lg border border-border bg-card p-6 text-sm text-muted-foreground">
          설정 로딩 중…
        </div>
      )}

      {settings.isError && (
        <div
          data-testid="settings-error"
          className="rounded-lg border border-red-200 bg-red-50 p-6 text-sm text-red-700 dark:border-red-900/40 dark:bg-red-900/20 dark:text-red-300"
        >
          설정을 불러오지 못했습니다.
        </div>
      )}

      {settings.isSuccess && <SettingsContent data={settings.data} />}
    </section>
  )
}

// ---------------------------------------------------------------------------
// User Preference section (v0.9 Phase D)
// ---------------------------------------------------------------------------

function UserPreferenceSection() {
  const { data: prefs, isLoading, isError } = useUserPreferences()
  const { data: watchlistsData } = useWatchlists()
  const updateMutation = useUpdateUserPreferences()

  const [defaultWatchlistId, setDefaultWatchlistId] = useState<number | null | ''>('')
  const [defaultMarket, setDefaultMarket] = useState('')
  const [defaultStrategy, setDefaultStrategy] = useState('')
  const [notifEnabled, setNotifEnabled] = useState(false)
  const [initialized, setInitialized] = useState(false)
  const [saveMsg, setSaveMsg] = useState<string | null>(null)
  const [saveError, setSaveError] = useState<string | null>(null)

  // Sync form state once preferences load (only on first load)
  if (prefs && !initialized) {
    setDefaultWatchlistId(prefs.default_watchlist_id ?? '')
    setDefaultMarket(prefs.default_market ?? '')
    setDefaultStrategy(prefs.default_strategy ?? '')
    const notifJson = prefs.notification_preferences_json
    if (notifJson && typeof notifJson === 'object' && 'enabled' in (notifJson as object)) {
      setNotifEnabled(Boolean((notifJson as Record<string, unknown>).enabled))
    }
    setInitialized(true)
  }

  const watchlists = watchlistsData?.watchlists ?? []

  async function handleSave(e: React.FormEvent) {
    e.preventDefault()
    setSaveMsg(null)
    setSaveError(null)
    try {
      await updateMutation.mutateAsync({
        default_watchlist_id: defaultWatchlistId === '' ? null : Number(defaultWatchlistId),
        default_market: defaultMarket || null,
        default_strategy: defaultStrategy || null,
        notification_preferences_json: { enabled: notifEnabled },
      })
      setSaveMsg('설정이 저장되었습니다.')
      setTimeout(() => setSaveMsg(null), 3000)
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.status === 401) {
          setSaveError('로그인이 필요합니다.')
        } else if (err.status === 404) {
          setSaveError('선택한 관심목록을 찾을 수 없습니다.')
        } else if (err.status === 422) {
          setSaveError('입력값이 올바르지 않습니다.')
        } else {
          setSaveError('설정 저장에 실패했습니다.')
        }
      } else {
        setSaveError('설정 저장에 실패했습니다.')
      }
    }
  }

  return (
    <section data-testid="user-preference-section" className="flex flex-col gap-4">
      <header className="flex flex-col gap-1">
        <h3 className="text-base font-semibold">사용자 설정</h3>
        <p className="text-xs text-muted-foreground">
          대시보드 기본값을 설정합니다. 알림 설정은 저장만 됩니다 (실제 발송 없음).
        </p>
      </header>

      {isLoading && (
        <p className="text-sm text-muted-foreground">사용자 설정 로딩 중…</p>
      )}

      {isError && (
        <div
          data-testid="user-preference-error"
          className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700 dark:border-red-900/40 dark:bg-red-900/20 dark:text-red-300"
        >
          사용자 설정을 불러오지 못했습니다.
        </div>
      )}

      {!isLoading && !isError && (
        <form
          data-testid="user-preference-form"
          onSubmit={handleSave}
          className="flex flex-col gap-4 rounded-lg border border-border bg-card p-5"
        >
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            {/* Default watchlist */}
            <label className="flex flex-col gap-1.5">
              <span className="text-xs font-medium text-muted-foreground">기본 관심목록</span>
              <select
                data-testid="pref-default-watchlist"
                value={defaultWatchlistId === null ? '' : String(defaultWatchlistId)}
                onChange={e => setDefaultWatchlistId(e.target.value === '' ? '' : Number(e.target.value))}
                className="rounded-md border border-border bg-background px-3 py-1.5 text-sm outline-none focus:ring-2 focus:ring-primary"
              >
                <option value="">— 선택 안 함 —</option>
                {watchlists.map(wl => (
                  <option key={wl.id} value={wl.id}>
                    {wl.name}{wl.is_default ? ' (기본)' : ''}
                  </option>
                ))}
              </select>
            </label>

            {/* Default market */}
            <label className="flex flex-col gap-1.5">
              <span className="text-xs font-medium text-muted-foreground">기본 시장</span>
              <select
                data-testid="pref-default-market"
                value={defaultMarket}
                onChange={e => setDefaultMarket(e.target.value)}
                className="rounded-md border border-border bg-background px-3 py-1.5 text-sm outline-none focus:ring-2 focus:ring-primary"
              >
                {MARKET_OPTIONS.map(m => (
                  <option key={m} value={m}>{m || '— 선택 안 함 —'}</option>
                ))}
              </select>
            </label>

            {/* Default strategy */}
            <label className="flex flex-col gap-1.5">
              <span className="text-xs font-medium text-muted-foreground">기본 전략</span>
              <select
                data-testid="pref-default-strategy"
                value={defaultStrategy}
                onChange={e => setDefaultStrategy(e.target.value)}
                className="rounded-md border border-border bg-background px-3 py-1.5 text-sm outline-none focus:ring-2 focus:ring-primary"
              >
                {STRATEGY_OPTIONS.map(s => (
                  <option key={s} value={s}>{s || '— 선택 안 함 —'}</option>
                ))}
              </select>
            </label>

            {/* Notification on/off (UI-only, no live send) */}
            <label className="flex flex-col gap-1.5">
              <span className="text-xs font-medium text-muted-foreground">알림 (저장 전용)</span>
              <div className="flex items-center gap-2 py-1.5">
                <input
                  data-testid="pref-notification-enabled"
                  type="checkbox"
                  id="notif-enabled"
                  checked={notifEnabled}
                  onChange={e => setNotifEnabled(e.target.checked)}
                  className="h-4 w-4 rounded border-border"
                />
                <label htmlFor="notif-enabled" className="text-sm">
                  알림 활성화
                </label>
                <span className="text-xs text-muted-foreground">(실제 발송 없음)</span>
              </div>
            </label>
          </div>

          <div className="flex items-center gap-3">
            <button
              type="submit"
              data-testid="pref-save-btn"
              disabled={updateMutation.isPending}
              className="flex items-center gap-1.5 rounded-md bg-primary px-4 py-1.5 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90 disabled:opacity-50"
            >
              <Save className="h-3.5 w-3.5" />
              {updateMutation.isPending ? '저장 중…' : '저장'}
            </button>
            {saveMsg && (
              <span
                data-testid="pref-save-success"
                className="text-sm text-green-600 dark:text-green-400"
              >
                {saveMsg}
              </span>
            )}
            {saveError && (
              <span
                data-testid="pref-save-error"
                role="alert"
                className="text-sm text-red-600 dark:text-red-300"
              >
                {saveError}
              </span>
            )}
          </div>
        </form>
      )}
    </section>
  )
}

// ---------------------------------------------------------------------------
// System settings (read-only) — unchanged from v0.1
// ---------------------------------------------------------------------------

function SettingsContent({ data }: { data: SettingsResponse }) {
  const dangerCount = [
    data.feature_real_order_execution,
    data.feature_full_auto,
    data.feature_paper_trading,
    data.feature_backtest,
    data.feature_custom_ai_training,
  ].filter(Boolean).length

  return (
    <div className="flex flex-col gap-5">
      <section className="flex flex-col gap-2">
        <h3 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">
          앱 / 환경
        </h3>
        <KeyValueGrid
          testid="settings-app-grid"
          rows={[
            { label: 'app_env', value: data.app_env },
            { label: 'app_name', value: data.app_name },
            { label: 'timezone', value: data.timezone },
            { label: 'log_level', value: data.log_level },
            {
              label: 'scheduler_enabled',
              value: (
                <SafetyFlagBadge
                  enabled={data.scheduler_enabled}
                  flag="scheduler_enabled"
                  dangerWhen="true"
                />
              ),
              hint: 'true 면 cron 잡 자동 실행',
            },
          ]}
        />
      </section>

      <section className="flex flex-col gap-2">
        <h3 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">
          KIS 연동 (read-only)
        </h3>
        <KeyValueGrid
          testid="settings-kis-grid"
          rows={[
            {
              label: 'kis_use_paper',
              value: (
                <SafetyFlagBadge
                  enabled={data.kis_use_paper}
                  flag="kis_use_paper"
                  dangerWhen="false"
                />
              ),
              hint: 'false 면 실서버 호출 — v0.1 범위 밖',
            },
            {
              label: 'kis_app_key',
              value: <MaskedSecret label="kis_app_key" value={data.kis_app_key} />,
            },
            {
              label: 'kis_app_secret',
              value: <MaskedSecret label="kis_app_secret" value={data.kis_app_secret} />,
            },
            {
              label: 'kis_account_no',
              value: <MaskedSecret label="kis_account_no" value={data.kis_account_no} />,
            },
          ]}
        />
      </section>

      <section className="flex flex-col gap-2">
        <h3 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">
          Telegram (read-only)
        </h3>
        <KeyValueGrid
          testid="settings-telegram-grid"
          rows={[
            {
              label: 'telegram_enabled',
              value: (
                <SafetyFlagBadge
                  enabled={data.telegram_enabled}
                  flag="telegram_enabled"
                  dangerWhen="true"
                />
              ),
              hint: 'true 면 실 발송 — 검증용 채팅방으로 한정',
            },
            {
              label: 'telegram_bot_token',
              value: (
                <MaskedSecret
                  label="telegram_bot_token"
                  value={data.telegram_bot_token}
                />
              ),
            },
            {
              label: 'telegram_chat_id',
              value: (
                <MaskedSecret
                  label="telegram_chat_id"
                  value={data.telegram_chat_id}
                />
              ),
            },
          ]}
        />
      </section>

      <section className="flex flex-col gap-2">
        <h3 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">
          v0.1 안전 플래그 ({dangerCount > 0 ? `⚠ ${dangerCount}건 위험 상태` : '모두 OFF'})
        </h3>
        <KeyValueGrid
          testid="settings-safety-grid"
          rows={[
            {
              label: 'feature_real_order_execution',
              value: (
                <SafetyFlagBadge
                  enabled={data.feature_real_order_execution}
                  flag="feature_real_order_execution"
                />
              ),
              hint: '실주문 실행 게이트 (절대 true 금지)',
            },
            {
              label: 'feature_full_auto',
              value: (
                <SafetyFlagBadge
                  enabled={data.feature_full_auto}
                  flag="feature_full_auto"
                />
              ),
              hint: 'FULL_AUTO 자동매매',
            },
            {
              label: 'feature_paper_trading',
              value: (
                <SafetyFlagBadge
                  enabled={data.feature_paper_trading}
                  flag="feature_paper_trading"
                />
              ),
              hint: 'v0.1 미구현',
            },
            {
              label: 'feature_backtest',
              value: (
                <SafetyFlagBadge
                  enabled={data.feature_backtest}
                  flag="feature_backtest"
                />
              ),
              hint: 'v0.1 미구현',
            },
            {
              label: 'feature_custom_ai_training',
              value: (
                <SafetyFlagBadge
                  enabled={data.feature_custom_ai_training}
                  flag="feature_custom_ai_training"
                />
              ),
              hint: 'v0.1 미구현',
            },
          ]}
        />
      </section>
    </div>
  )
}

function MaskedSecret({ label, value }: { label: string; value: string }) {
  const isMasked = value.includes('*')
  return (
    <span
      data-testid={`secret-${label}`}
      data-masked={isMasked ? 'true' : 'false'}
      className="font-mono text-sm tabular-nums"
    >
      {value || '(empty)'}
      {!isMasked && value ? (
        <span className="ml-2 text-xs font-semibold text-red-600 dark:text-red-300">
          ⚠ unmasked
        </span>
      ) : null}
    </span>
  )
}
