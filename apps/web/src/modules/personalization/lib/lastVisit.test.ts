import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { newestVisit, readLocalVisit, REPORT_WINDOW_MS, saveLocalVisit, sendVisit, shouldReport } from './lastVisit'

vi.mock('~/lib/env', () => ({ env: { VITE_API_URL: 'https://api.test' } }))

function stubStorage(blocked = false) {
  const store = new Map<string, string>()
  vi.stubGlobal('localStorage', {
    getItem: (k: string) => {
      if (blocked) throw new Error('blocked')
      return store.get(k) ?? null
    },
    setItem: (k: string, v: string) => {
      if (blocked) throw new Error('blocked')
      store.set(k, v)
    },
    removeItem: (k: string) => void store.delete(k),
  })
  return store
}

describe('local copy', () => {
  beforeEach(() => void stubStorage())
  afterEach(() => vi.unstubAllGlobals())

  it('round-trips a restorable page, per user', () => {
    saveLocalVisit('u1', { path: '/app/focus', search: '' }, new Date('2026-10-06T10:00:00Z'))
    expect(readLocalVisit('u1')).toEqual({ path: '/app/focus', search: '', at: '2026-10-06T10:00:00.000Z' })
    expect(readLocalVisit('u2')).toBeNull()
  })
  it('re-validates what it reads back', () => {
    const store = stubStorage()
    store.set('last-visit:u1', JSON.stringify({ path: '/app/account', search: '', at: '2026-10-06T10:00:00Z' }))
    expect(readLocalVisit('u1')).toBeNull()
    store.set('last-visit:u1', JSON.stringify({ path: '/app/focus', search: '', at: 'yesterday' }))
    expect(readLocalVisit('u1')).toBeNull()
    store.set('last-visit:u1', '{broken')
    expect(readLocalVisit('u1')).toBeNull()
  })
  it('survives blocked storage', () => {
    stubStorage(true)
    expect(() => saveLocalVisit('u1', { path: '/app', search: '' })).not.toThrow()
    expect(readLocalVisit('u1')).toBeNull()
  })
})

describe('newestVisit', () => {
  const server = { path: '/app/revision', search: '', at: '2026-10-06T10:00:00.000Z' }
  const local = (at: string) => ({ path: '/app/focus', search: '', at })
  it('prefers the server unless the device copy is newer', () => {
    expect(newestVisit(server, local('2026-10-06T09:00:00.000Z'))).toBe(server)
    expect(newestVisit(server, local('2026-10-06T11:00:00.000Z'))?.path).toBe('/app/focus')
  })
  it('handles either side missing', () => {
    expect(newestVisit(null, null)).toBeNull()
    expect(newestVisit(server, null)).toBe(server)
    expect(newestVisit(null, local('2026-10-06T09:00:00.000Z'))?.path).toBe('/app/focus')
    expect(newestVisit({ ...server, at: null }, local('2026-10-06T09:00:00.000Z'))?.path).toBe('/app/focus')
  })
})

describe('shouldReport', () => {
  const visit = { path: '/app/tracker', search: '' }
  it('skips the same page inside the window only', () => {
    expect(shouldReport(null, visit, 1000)).toBe(true)
    const memory = { href: '/app/tracker?', at: 1000 }
    expect(shouldReport(memory, visit, 1000 + REPORT_WINDOW_MS - 1)).toBe(false)
    expect(shouldReport(memory, visit, 1000 + REPORT_WINDOW_MS)).toBe(true)
    expect(shouldReport(memory, { path: '/app/focus', search: '' }, 1001)).toBe(true)
  })
})

describe('sendVisit', () => {
  afterEach(() => vi.unstubAllGlobals())
  const visit = { path: '/app/tracker', search: 'x=1' }

  it('uses a beacon with the token in a text body and no header', () => {
    const beacon = vi.fn(() => true)
    const fetchMock = vi.fn()
    vi.stubGlobal('navigator', { sendBeacon: beacon })
    vi.stubGlobal('fetch', fetchMock)
    sendVisit('tok', visit)
    expect(beacon).toHaveBeenCalledWith(
      'https://api.test/api/v1/me/last-visit/',
      JSON.stringify({ path: '/app/tracker', search: 'x=1', t: 'tok' }),
    )
    expect(fetchMock).not.toHaveBeenCalled()
  })
  it.each([
    ['refuses', { sendBeacon: () => false }],
    [
      'throws',
      {
        sendBeacon: () => {
          throw new Error('nope')
        },
      },
    ],
    ['is missing', {}],
  ])('falls back to a keepalive fetch when the beacon %s', (_name, nav) => {
    const fetchMock = vi.fn(() => Promise.resolve(new Response(null, { status: 204 })))
    vi.stubGlobal('navigator', nav)
    vi.stubGlobal('fetch', fetchMock)
    sendVisit('tok', visit)
    expect(fetchMock).toHaveBeenCalledOnce()
    const [, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit]
    expect(init).toMatchObject({ method: 'POST', keepalive: true })
    expect((init.headers as Record<string, string>).Authorization).toBe('Bearer tok')
    expect(String(init.body)).not.toContain('tok')
  })
  it('never throws when the fetch fails', () => {
    vi.stubGlobal('navigator', {})
    vi.stubGlobal('fetch', () => Promise.reject(new Error('offline')))
    expect(() => sendVisit('tok', visit)).not.toThrow()
  })
})
