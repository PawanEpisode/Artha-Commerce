import { renderHook, waitFor } from '@testing-library/react'
import { StrictMode } from 'react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const state = vi.hoisted(() => ({
  searchStr: '',
  replace: vi.fn(),
  postClick: vi.fn(),
  track: vi.fn(),
}))

vi.mock('@tanstack/react-router', () => ({
  useLocation: ({ select }: { select: (l: { searchStr: string }) => unknown }) =>
    select({ searchStr: state.searchStr }),
  useRouter: () => ({ history: { replace: state.replace } }),
}))
vi.mock('~/modules/observability', () => ({ track: state.track }))
vi.mock('../lib/api', () => ({ postClick: state.postClick }))

import { captureLandingId, resetLandingState } from '../lib/landing'
import { useNotificationLanding } from './useNotificationLanding'

const at = (url: string) => {
  window.history.replaceState(null, '', url)
  state.searchStr = window.location.search
}

beforeEach(() => {
  resetLandingState()
  state.replace.mockReset().mockImplementation((next: string) => window.history.replaceState(null, '', next))
  state.postClick.mockReset().mockResolvedValue({})
  state.track.mockClear()
  at('/app/focus')
})

describe('useNotificationLanding (?n=<id>)', () => {
  it('reports the click once and removes the parameter', async () => {
    at('/app/focus?n=abc123&subject=gst')
    renderHook(() => useNotificationLanding())
    await waitFor(() => expect(state.replace).toHaveBeenCalledWith('/app/focus?subject=gst'))
    expect(state.postClick).toHaveBeenCalledTimes(1)
    expect(state.postClick).toHaveBeenCalledWith('abc123')
  })

  it('still reports only once under React strict mode and across re-renders', async () => {
    at('/app/focus?n=abc123')
    const { rerender } = renderHook(() => useNotificationLanding(), { wrapper: StrictMode })
    rerender()
    await waitFor(() => expect(state.replace).toHaveBeenCalled())
    expect(state.postClick).toHaveBeenCalledTimes(1)
  })

  it('does nothing without a parameter', () => {
    renderHook(() => useNotificationLanding())
    expect(state.postClick).not.toHaveBeenCalled()
    expect(state.replace).not.toHaveBeenCalled()
  })

  it('ignores a value that is not shaped like an id', () => {
    at('/app/focus?n=../../etc/passwd')
    renderHook(() => useNotificationLanding())
    expect(state.postClick).not.toHaveBeenCalled()
  })

  it('uses the id captured at first load when the router already dropped the parameter', async () => {
    captureLandingId('?n=from-first-load')
    renderHook(() => useNotificationLanding())
    await waitFor(() => expect(state.postClick).toHaveBeenCalledWith('from-first-load'))
    expect(state.replace).not.toHaveBeenCalled() // nothing left in the address to remove
  })

  it('removes the parameter and says nothing when the API call fails', async () => {
    at('/app/focus?n=abc123')
    state.postClick.mockRejectedValue(new Error('offline'))
    renderHook(() => useNotificationLanding())
    await waitFor(() => expect(state.replace).toHaveBeenCalledWith('/app/focus'))
    expect(state.track).not.toHaveBeenCalled()
  })

  it('sends push_clicked with what the API returned', async () => {
    at('/app/focus?n=abc123')
    state.postClick.mockResolvedValue({ category: 'timer', seconds_since_sent: 12 })
    renderHook(() => useNotificationLanding())
    await waitFor(() =>
      expect(state.track).toHaveBeenCalledWith('push_clicked', { category: 'timer', seconds_since_sent: 12 }),
    )
  })

  it('does not report the same notification again when it comes back later', async () => {
    at('/app/focus?n=abc123')
    const first = renderHook(() => useNotificationLanding())
    await waitFor(() => expect(state.replace).toHaveBeenCalled())
    first.unmount()
    at('/app/tracker?n=abc123')
    renderHook(() => useNotificationLanding())
    await waitFor(() => expect(state.replace).toHaveBeenCalledTimes(2))
    expect(state.postClick).toHaveBeenCalledTimes(1)
  })
})
