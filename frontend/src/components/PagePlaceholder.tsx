import type { ReactNode } from 'react'

interface PagePlaceholderProps {
  title: string
  description?: string
  apis: string[]
  children?: ReactNode
}

// Phase A 화면 기본 골격. 다음 phase 에서 useQuery + 컴포넌트가 자리잡으면
// 화면별 인덱스 파일에서 이 컴포넌트를 제거하거나 emptyState 로 사용한다.
export function PagePlaceholder({
  title,
  description = 'v0.2 Phase A — placeholder. 다음 phase 에서 데이터 연동 예정.',
  apis,
  children,
}: PagePlaceholderProps) {
  return (
    <section className="flex flex-col gap-4">
      <header className="flex flex-col gap-1">
        <h2 className="text-2xl font-semibold">{title}</h2>
        <p className="text-sm text-muted-foreground">{description}</p>
      </header>
      <div className="rounded-lg border border-dashed border-border bg-card p-6">
        <h3 className="mb-2 text-sm font-medium">예정된 백엔드 API</h3>
        <ul className="space-y-1 text-sm text-muted-foreground">
          {apis.map(api => (
            <li key={api} className="font-mono">
              {api}
            </li>
          ))}
        </ul>
        {children ? <div className="mt-4">{children}</div> : null}
      </div>
    </section>
  )
}
