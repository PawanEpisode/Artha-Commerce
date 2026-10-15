import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { DayRolloverBar, StatusBanner } from './StatusBanner'

describe('StatusBanner', () => {
  it('renders nothing when all is well', () => {
    const { container } = render(<StatusBanner banner={{ kind: 'none' }} planDate="2026-10-14" />)
    expect(container).toBeEmptyDOMElement()
  })

  it('says offline and how many changes wait', () => {
    render(<StatusBanner banner={{ kind: 'offline', waiting: 2 }} planDate="2026-10-14" />)
    expect(screen.getByText(/offline/i)).toBeInTheDocument()
    expect(screen.getByText(/2 changes waiting to sync/i)).toBeInTheDocument()
  })

  it('says syncing after reconnect', () => {
    render(<StatusBanner banner={{ kind: 'syncing', waiting: 1 }} planDate="2026-10-14" />)
    expect(screen.getByText(/back online, syncing 1 change/i)).toBeInTheDocument()
  })

  it('offers a refresh on a stale plan', () => {
    const onRefresh = vi.fn()
    render(
      <StatusBanner
        banner={{ kind: 'stale', label: 'Updated 7 hours ago' }}
        planDate="2026-10-14"
        onRefresh={onRefresh}
      />,
    )
    fireEvent.click(screen.getByRole('button', { name: 'Refresh' }))
    expect(onRefresh).toHaveBeenCalled()
  })

  it('tells the student a previous-day plan is not today', () => {
    render(<StatusBanner banner={{ kind: 'previous_day' }} planDate="2026-10-14" />)
    expect(screen.getByText(/connect to get today/i)).toBeInTheDocument()
  })
})

describe('DayRolloverBar', () => {
  it('shows today on click', () => {
    const onShow = vi.fn()
    render(<DayRolloverBar onShow={onShow} />)
    fireEvent.click(screen.getByRole('button', { name: 'Show today' }))
    expect(onShow).toHaveBeenCalled()
  })
})
