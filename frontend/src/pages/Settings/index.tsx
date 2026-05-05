import { AlertTriangle } from 'lucide-react'
import { useSettings } from '@/hooks/useSettings'
import { KeyValueGrid } from '@/components/common/KeyValueGrid'
import { SafetyFlagBadge } from '@/components/common/SafetyFlagBadge'
import type { SettingsResponse } from '@/api/types'

export function SettingsPage() {
  const settings = useSettings()

  return (
    <section className="flex flex-col gap-4">
      <header className="flex flex-col gap-1">
        <h2 className="text-2xl font-semibold">설정</h2>
        <p className="text-sm text-muted-foreground">
          현재 백엔드가 노출하는 설정 (read-only). 비밀값은 모두 백엔드에서 마스킹된
          상태로 전달된다.
        </p>
      </header>

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
            본 화면은 백엔드 응답을 그대로 보여주는 read-only 진단 페이지입니다.
            설정 변경은 <code>.env</code> 수정 후 백엔드 재시작으로만 가능하며,
            대시보드에서 직접 수정하는 폼은 v0.2 범위 밖입니다.
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

function SettingsContent({ data }: { data: SettingsResponse }) {
  // Any "ON" of these v0.1 안전 플래그 should highlight in red — they all
  // must be `false` while the backend is frozen at v0.1-backend-final.
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
  // 백엔드가 이미 마스킹한 값을 그대로 표시한다. 평문 비밀이 들어오면 즉시
  // 시각적으로 드러나도록 unmasked 마커도 노출.
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
