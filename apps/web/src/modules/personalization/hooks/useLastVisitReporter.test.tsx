import { renderHook } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { useLastVisitReporter } from './useLastVisitReporter'

const state = vi.hoisted(() => ({
  flag: true,
  pathname: '/app/syllabus/fin-acc/ch-3',
  searchStr: '',
  token: 'tok' as string | undefined,
  send: vi.fn(),
  save: vi.fn(),
}))

vi.mock('@tanstack/react-router', () => ({
  useLocation: ({ select }: { select: (l: { pathname: string; searchStr: string }) => unknown }) =>
    select({ pathname: state.pathname, searchStr: state.searchStr }),
}))
vi.mock('~/modules/auth', () => ({
  useAuth: () => ({ session: state.token ? { access_token: state.token, user: { id: 'u1' } } : null }),
}))
vi.mock('~/modules/observability', () => ({ useFeatureFlag: () => state.flag }))
vi.mock('../lib/lastVisit', async (original) => ({
  ...(await original<Record<string, unknown>>()),
  sendVisit: state.send,
  saveLocalVisit: state.save,
}))

function hide() {
  Object.defineProperty(document, 'visibilityState', { value: 'hidden', configurable: true })
  document.dispatchEvent(new Event('visibilitychange'))
}
const show = () => {
  Object.defineProperty(document, 'visibilityState', { value: 'visible', configurable: true })
  document.dispatchEvent(new Event('visibilitychange'))
}

describe('useLastVisitReporter', () => {
  beforeEach(() => {
    Object.assign(state, { flag: true, pathname: '/app/syllabus/fin-acc/ch-3', searchStr: '', token: 'tok' })
    state.send.mockClear()
    state.save.mockClear()
    show()
  })

  it('reports once when the tab is hidden, and keeps a device copy', () => {
    renderHook(() => useLastVisitReporter())
    show()
    expect(state.send).not.toHaveBeenCalled() // showing, or just navigating, never writes
    hide()
    expect(state.send).toHaveBeenCalledWith('tok', { path: '/app/syllabus/fin-acc/ch-3', search: '' })
    expect(state.save).toHaveBeenCalledWith('u1', { path: '/app/syllabus/fin-acc/ch-3', search: '' })
  })

  it('does not report the same page again within a minute, but still refreshes the device copy', () => {
    renderHook(() => useLastVisitReporter())
    hide()
    hide()
    expect(state.send).toHaveBeenCalledOnce()
    expect(state.save).toHaveBeenCalledTimes(2)
  })

  it('reports on pagehide too', () => {
    renderHook(() => useLastVisitReporter())
    window.dispatchEvent(new Event('pagehide'))
    expect(state.send).toHaveBeenCalledOnce()
  })

  it('ignores pages that are not worth restoring', () => {
    state.pathname = '/app/account'
    renderHook(() => useLastVisitReporter())
    hide()
    expect(state.send).not.toHaveBeenCalled()
    expect(state.save).not.toHaveBeenCalled()
  })

  it('does nothing without a session or with the flag off', () => {
    state.token = undefined
    const first = renderHook(() => useLastVisitReporter())
    hide()
    first.unmount()
    state.token = 'tok'
    state.flag = false
    renderHook(() => useLastVisitReporter())
    hide()
    expect(state.send).not.toHaveBeenCalled()
  })

  it('stops listening when unmounted', () => {
    const view = renderHook(() => useLastVisitReporter())
    view.unmount()
    hide()
    expect(state.send).not.toHaveBeenCalled()
  })
})
