import { describe, expect, it } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { Routes, Route } from 'react-router-dom'
import { renderWithProviders } from './renderWithProviders'
import { server } from './mswServer'
import { JobsPage } from '@/pages/Jobs'

function renderJobsAt(path = '/jobs') {
  return renderWithProviders(
    <Routes>
      <Route path="/jobs" element={<JobsPage />} />
      <Route path="/jobs/:jobId" element={<JobsPage />} />
    </Routes>,
    { initialEntries: [path] },
  )
}

describe('JobsPage', () => {
  it('renders the table with status / data_status / notification_status / dry_run badges (happy)', async () => {
    server.use(
      http.get('*/api/jobs', () =>
        HttpResponse.json({
          items: [
            {
              job_id: 101,
              job_name: 'send_recommendation_report',
              started_at: '2026-05-04T22:52:00Z',
              finished_at: '2026-05-04T22:52:01Z',
              status: 'SUCCESS',
              error_message: null,
              result_summary: {
                notification_status: 'DRY_RUN',
                dry_run: true,
              },
            },
            {
              job_id: 102,
              job_name: 'update_recommendation_results',
              started_at: '2026-05-04T22:53:00Z',
              finished_at: '2026-05-04T22:53:02Z',
              status: 'PARTIAL',
              error_message: '1 recommendations had no reference price',
              result_summary: { data_status: 'PARTIAL' },
            },
          ],
          limit: 50,
          offset: 0,
        }),
      ),
    )

    renderJobsAt('/jobs')

    await waitFor(() =>
      expect(screen.getByTestId('job-row-101')).toBeInTheDocument(),
    )
    expect(screen.getByText('send_recommendation_report')).toBeInTheDocument()
    expect(screen.getByText('update_recommendation_results')).toBeInTheDocument()
    // status / data_status / notification_status / dry_run 배지 + 텍스트 확인
    expect(screen.getByTestId('status-job-SUCCESS')).toBeInTheDocument()
    expect(screen.getByTestId('status-job-PARTIAL')).toBeInTheDocument()
    expect(screen.getByTestId('status-data-PARTIAL')).toBeInTheDocument()
    expect(screen.getByTestId('status-notification-DRY_RUN')).toBeInTheDocument()
    expect(screen.getByTestId('dry-run-101')).toHaveTextContent('DRY')
  })

  it('opens the detail panel when a row is clicked (result_summary JSON visible)', async () => {
    server.use(
      http.get('*/api/jobs', () =>
        HttpResponse.json({
          items: [
            {
              job_id: 101,
              job_name: 'send_recommendation_report',
              started_at: '2026-05-04T22:52:00Z',
              finished_at: '2026-05-04T22:52:01Z',
              status: 'SUCCESS',
              error_message: null,
              result_summary: {
                notification_status: 'DRY_RUN',
                dry_run: true,
                run_id: 7,
              },
            },
          ],
          limit: 50,
          offset: 0,
        }),
      ),
      http.get('*/api/jobs/101', () =>
        HttpResponse.json({
          job_id: 101,
          job_name: 'send_recommendation_report',
          started_at: '2026-05-04T22:52:00Z',
          finished_at: '2026-05-04T22:52:01Z',
          status: 'SUCCESS',
          error_message: null,
          result_summary: {
            notification_status: 'DRY_RUN',
            dry_run: true,
            run_id: 7,
          },
          successes: [],
          skipped: [],
          failures: [],
          batches: [],
        }),
      ),
    )

    renderJobsAt('/jobs')
    const row = await screen.findByTestId('job-row-101')
    await userEvent.click(row)

    await waitFor(() =>
      expect(screen.getByTestId('job-detail-panel')).toBeInTheDocument(),
    )
    const json = screen.getByTestId('json-viewer')
    expect(json).toHaveTextContent('"notification_status": "DRY_RUN"')
    expect(json).toHaveTextContent('"dry_run": true')
    expect(json).toHaveTextContent('"run_id": 7')
  })

  it('shows the empty state when /api/jobs returns no items', async () => {
    server.use(
      http.get('*/api/jobs', () =>
        HttpResponse.json({ items: [], limit: 50, offset: 0 }),
      ),
    )

    renderJobsAt('/jobs')
    await waitFor(() => expect(screen.getByTestId('jobs-empty')).toBeInTheDocument())
    expect(screen.queryByTestId('jobs-table-body')).not.toBeInTheDocument()
  })

  it('shows the error state when /api/jobs returns 500', async () => {
    server.use(
      http.get('*/api/jobs', () =>
        HttpResponse.json({ detail: 'simulated outage' }, { status: 500 }),
      ),
    )

    renderJobsAt('/jobs')
    await waitFor(() => expect(screen.getByTestId('jobs-error')).toBeInTheDocument())
  })
})
