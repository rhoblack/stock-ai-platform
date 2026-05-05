import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MarketStatusBanner } from '@/components/common/MarketStatusBanner'

describe('MarketStatusBanner', () => {
  it('영업일이면 open 상태로 OK 메시지 표시', () => {
    render(<MarketStatusBanner date="2026-06-15" />)
    const banner = screen.getByTestId('market-status-banner')
    expect(banner).toHaveAttribute('data-state', 'open')
    expect(banner).toHaveTextContent('오늘은 영업일')
    expect(banner).toHaveTextContent('2026-06-15')
    expect(banner).toHaveTextContent('정규장 운영 중')
  })

  it('한국 공휴일이면 holiday 상태 + 휴장 사유 + 다음 영업일 표시', () => {
    render(<MarketStatusBanner date="2026-01-01" />)
    const banner = screen.getByTestId('market-status-banner')
    expect(banner).toHaveAttribute('data-state', 'holiday')
    expect(banner).toHaveTextContent('한국 주식시장 휴장일')
    expect(banner).toHaveTextContent('신정')
    expect(banner).toHaveTextContent('다음 영업일: 2026-01-02')
  })

  it('주말이면 weekend 상태 + 다음 영업일 표시', () => {
    render(<MarketStatusBanner date="2026-01-03" />) // Saturday
    const banner = screen.getByTestId('market-status-banner')
    expect(banner).toHaveAttribute('data-state', 'weekend')
    expect(banner).toHaveTextContent('주말')
    expect(banner).toHaveTextContent('다음 영업일: 2026-01-05')
  })

  it('연말 폐장 + 신정 + 주말 동시 시 다음 영업일을 건너뛰어 계산', () => {
    render(<MarketStatusBanner date="2026-12-31" />)
    const banner = screen.getByTestId('market-status-banner')
    expect(banner).toHaveAttribute('data-state', 'holiday')
    expect(banner).toHaveTextContent('연말 폐장')
    // 2026-12-31 Thu → 2027-01-01 Fri 신정 → 주말 → 2027-01-04 Mon
    expect(banner).toHaveTextContent('다음 영업일: 2027-01-04')
  })
})
