import { useMemo, useState } from 'react'
import { cn } from '@/lib/utils'

interface JsonViewerProps {
  value: unknown
  className?: string
  collapsedByDefault?: boolean
}

// 외부 의존성 없는 가벼운 JSON viewer. 잡 result_summary 진단용.
// 깊이 무한 + 가독성 위주 — 매우 큰 페이로드는 백엔드에서 잘라 보낸다고 가정.
export function JsonViewer({ value, className, collapsedByDefault = false }: JsonViewerProps) {
  const pretty = useMemo(() => safeStringify(value), [value])
  const [collapsed, setCollapsed] = useState(collapsedByDefault)

  if (value === null || value === undefined) {
    return (
      <div className={cn('text-sm text-muted-foreground', className)}>(empty)</div>
    )
  }

  return (
    <div className={cn('flex flex-col gap-2', className)}>
      <div className="flex items-center justify-between">
        <span className="text-xs uppercase tracking-wide text-muted-foreground">
          JSON
        </span>
        <button
          type="button"
          className="text-xs text-muted-foreground hover:text-foreground"
          onClick={() => setCollapsed(c => !c)}
        >
          {collapsed ? '펼치기' : '접기'}
        </button>
      </div>
      {!collapsed && (
        <pre
          data-testid="json-viewer"
          className="max-h-96 overflow-auto rounded-md border border-border bg-muted/40 p-3 text-xs leading-relaxed"
        >
          <code className="font-mono">{pretty}</code>
        </pre>
      )}
    </div>
  )
}

function safeStringify(value: unknown): string {
  try {
    return JSON.stringify(value, null, 2)
  } catch (err) {
    return `[unserializable: ${(err as Error).message}]`
  }
}
