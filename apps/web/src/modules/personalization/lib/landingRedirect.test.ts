import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { LANDING_REDIRECT_KEY, LANDING_REDIRECT_SCRIPT, mirrorLandingRedirect } from './landingRedirect'

function fakeStorage(initial: Record<string, string>) {
  const store = new Map(Object.entries(initial))
  return {
    get length() {
      return store.size
    },
    key: (i: number) => [...store.keys()][i] ?? null,
    getItem: (k: string) => store.get(k) ?? null,
    setItem: (k: string, v: string) => void store.set(k, v),
    removeItem: (k: string) => void store.delete(k),
  }
}

/** Runs the real script text against a fake page; returns where it redirected, if anywhere. */
function run(storage: Record<string, string>): string | null {
  let to: string | null = null
  vi.stubGlobal('localStorage', fakeStorage(storage))
  vi.stubGlobal('location', { replace: (url: string) => (to = url) })

  new Function(LANDING_REDIRECT_SCRIPT)()
  return to
}

const session = JSON.stringify({ access_token: 'a', refresh_token: 'r' })

describe('landing redirect script', () => {
  beforeEach(() => vi.unstubAllGlobals())
  afterEach(() => vi.unstubAllGlobals())

  it('sends a stored Supabase session to /app', () => {
    expect(run({ 'sb-abc-auth-token': session })).toBe('/app?from=landing')
  })
  it('leaves signed-out visitors alone', () => {
    expect(run({})).toBeNull()
    expect(run({ theme: 'dark' })).toBeNull()
  })
  it('ignores a broken or tokenless value without throwing', () => {
    expect(run({ 'sb-abc-auth-token': '{not json' })).toBeNull()
    expect(run({ 'sb-abc-auth-token': JSON.stringify({ access_token: 'a' }) })).toBeNull()
  })
  it('is switched off by the mirrored flag', () => {
    expect(run({ 'sb-abc-auth-token': session, [LANDING_REDIRECT_KEY]: 'off' })).toBeNull()
  })
})

describe('mirrorLandingRedirect', () => {
  afterEach(() => vi.unstubAllGlobals())
  it('writes "off" and clears it again', () => {
    const storage = fakeStorage({})
    vi.stubGlobal('localStorage', storage)
    mirrorLandingRedirect(false)
    expect(storage.getItem(LANDING_REDIRECT_KEY)).toBe('off')
    mirrorLandingRedirect(true)
    expect(storage.getItem(LANDING_REDIRECT_KEY)).toBeNull()
  })
})
