import { useJobDetail } from '@/hooks/useJobDetail'
import { DataStatusBadge } from '@/components/common/DataStatusBadge'
import { JsonViewer } from '@/components/common/JsonViewer'
import type { JobResultSummaryKeys } from '@/api/types'

interface JobDetailPanelProps {
  jobId: number | null
}

function formatTime(value: string | null | undefined): string {
  if (!value) return '—'
  const d = new Date(value)
  return Number.isNaN(d.getTime()) ? value : d.toLocaleString('ko-KR', { hour12: false })
}

export function JobDetailPanel({ jobId }: JobDetailPanelProps) {
  const detail = useJobDetail(jobId)

  if (jobId === null) {
    return (
      <aside
        data-testid="job-detail-empty"
        className="flex h-full items-center justify-center rounded-lg border border-dashed border-border bg-card p-6 text-sm text-muted-foreground"
      >
        잡 행을 클릭하면 상세가 표시됩니다.
      </aside>
    )
  }

  if (detail.isLoading) {
    return (
      <aside className="rounded-lg border border-border bg-card p-6 text-sm text-muted-foreground">
        로딩 중…
      </aside>
    )
  }

  if (detail.isError) {
    return (
      <aside
        data-testid="job-detail-error"
        className="rounded-lg border border-border bg-card p-6 text-sm text-red-600 dark:text-red-300"
      >
        잡 상세를 불러오지 못했습니다 ({String((detail.error as Error)?.message ?? 'unknown')}).
      </aside>
    )
  }

  const job = detail.data
  if (!job) return null
  const summary = (job.result_summary ?? {}) as JobResultSummaryKeys

  return (
    <aside
      data-testid="job-detail-panel"
      className="flex flex-col gap-4 rounded-lg border border-border bg-card p-6"
    >
      <header className="flex flex-col gap-2">
        <div className="flex items-center justify-between gap-3">
          <div className="flex flex-col">
            <span className="text-xs uppercase tracking-wide text-muted-foreground">
              #{job.job_id}
            </span>
            <h3 className="text-lg font-semibold">{job.job_name}</h3>
          </div>
          <DataStatusBadge status={job.status} variant="job" />
        </div>
        <dl className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs">
          <dt className="text-muted-foreground">시작</dt>
          <dd className="font-mono">{formatTime(job.started_at)}</dd>
          <dt className="text-muted-foreground">종료</dt>
          <dd className="font-mono">{formatTime(job.finished_at)}</dd>
          {summary.data_status && (
            <>
              <dt className="text-muted-foreground">data_status</dt>
              <dd>
                <DataStatusBadge status={summary.data_status} variant="data" />
              </dd>
            </>
          )}
          {summary.notification_status && (
            <>
              <dt className="text-muted-foreground">notification</dt>
              <dd>
                <DataStatusBadge status={summary.notification_status} variant="notification" />
              </dd>
            </>
          )}
          {summary.dry_run !== undefined && (
            <>
              <dt className="text-muted-foreground">dry_run</dt>
              <dd className="font-mono">{summary.dry_run ? 'true' : 'false'}</dd>
            </>
          )}
        </dl>
      </header>

      {job.error_message && (
        <div
          data-testid="job-detail-error-message"
          className="rounded-md border border-red-200 bg-red-50 p-3 text-xs text-red-700 dark:border-red-900/40 dark:bg-red-900/20 dark:text-red-300"
        >
          <strong className="font-semibold">error_message:</strong> {job.error_message}
        </div>
      )}

      <section className="flex flex-col gap-2">
        <h4 className="text-sm font-medium">result_summary</h4>
        <JsonViewer value={job.result_summary} />
      </section>

      {job.failures.length > 0 && (
        <section className="flex flex-col gap-2">
          <h4 className="text-sm font-medium">failures ({job.failures.length})</h4>
          <JsonViewer value={job.failures} collapsedByDefault />
        </section>
      )}
      {job.successes.length > 0 && (
        <section className="flex flex-col gap-2">
          <h4 className="text-sm font-medium">successes ({job.successes.length})</h4>
          <JsonViewer value={job.successes} collapsedByDefault />
        </section>
      )}
      {job.skipped.length > 0 && (
        <section className="flex flex-col gap-2">
          <h4 className="text-sm font-medium">skipped ({job.skipped.length})</h4>
          <JsonViewer value={job.skipped} collapsedByDefault />
        </section>
      )}
    </aside>
  )
}
