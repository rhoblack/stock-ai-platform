import { useParams } from 'react-router-dom'
import { PagePlaceholder } from '@/components/PagePlaceholder'

export function JobsPage() {
  const { jobId } = useParams<{ jobId: string }>()
  return (
    <PagePlaceholder
      title={jobId ? `잡 상세 — #${jobId}` : '시스템 로그 / 잡'}
      description="최근 6 잡 실행 + status / data_status / notification_status / dry_run + result_summary 진단."
      apis={['GET /api/jobs', 'GET /api/jobs/{job_id}']}
    />
  )
}
