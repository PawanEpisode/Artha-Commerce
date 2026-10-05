import { afterEach, describe, expect, it, vi } from 'vitest'

import { SIGNED_IN_MARK_SCRIPT } from './sessionMark'

function fakeStorage(initial: Record<string, string>) {
  const store = new Map(Object.entries(initial))
  return {
    get length() {
      return store.size
    },
    key: (i: number) => [...store.keys()][i] ?? null,
    getItem: (k: string) => store.get(k) ?? null,
  }
}

function run(storage: Record<string, string>): string | undefined {
  const dataset: { signedIn?: string } = {}
  vi.stubGlobal('localStorage', fakeStorage(storage))
  vi.stubGlobal('document', { documentElement: { dataset } })
  new Function(SIGNED_IN_MARK_SCRIPT)()
  return dataset.signedIn
}

const session = JSON.stringify({ access_token: 'a', refresh_token: 'r' })

describe('signed-in mark', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('marks a stored session and leaves a guest unmarked', () => {
    expect(run({ 'sb-abc-auth-token': session })).toBe('1')
    expect(run({})).toBeUndefined()
  })

  it('ignores a tokenless value', () => {
    expect(run({ 'sb-abc-auth-token': JSON.stringify({ access_token: 'a' }) })).toBeUndefined()
  })
})
