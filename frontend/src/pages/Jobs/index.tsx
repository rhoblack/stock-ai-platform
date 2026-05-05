import { useParams } from 'react-router-dom'
import { useJobs } from '@/hooks/useJobs'
import { JobsTable } from './JobsTable'
import { JobDetailPanel } from './JobDetailPanel'

export function JobsPage() {
  const { jobId } = useParams<{ jobId: string }>()
  const selectedId = jobId ? Number(jobId) : null
  const jobs = useJobs({ limit: 50 })

  return (
    <section className="flex flex-col gap-4">
      <header className="flex flex-col gap-1">
        <h2 className="text-2xl font-semibold">시스템 로그 / 잡</h2>
        <p className="text-sm text-muted-foreground">
          최근 50건. 30초마다 자동 새로고침.{' '}
          {jobs.dataUpdatedAt > 0 && (
            <span className="font-mono text-xs">
              (last fetch {new Date(jobs.dataUpdatedAt).toLocaleTimeString('ko-KR')})
            </span>
          )}
        </p>
      </header>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
        <div data-testid="jobs-list-region">
          {jobs.isLoading && (
            <div className="rounded-lg border border-border bg-card p-6 text-sm text-muted-foreground">
              잡 목록 로딩 중…
            </div>
          )}
          {jobs.isError && (
            <div
              data-testid="jobs-error"
              className="rounded-lg border border-red-200 bg-red-50 p-6 text-sm text-red-700 dark:border-red-900/40 dark:bg-red-900/20 dark:text-red-300"
            >
              잡 목록을 불러오지 못했습니다.
            </div>
          )}
          {jobs.isSuccess && <JobsTable rows={jobs.data.items} />}
        </div>
        <JobDetailPanel jobId={Number.isFinite(selectedId) ? selectedId : null} />
      </div>
    </section>
  )
}
