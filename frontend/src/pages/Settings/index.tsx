import { PagePlaceholder } from '@/components/PagePlaceholder'

export function SettingsPage() {
  return (
    <PagePlaceholder
      title="설정"
      description="env / timezone / KIS use_paper / scheduler_enabled / telegram_enabled / feature flags. KIS 키와 텔레그램 토큰은 백엔드 응답에서 마스킹된 형태로만 노출된다."
      apis={['GET /api/settings']}
    />
  )
}
