import { afterEach, describe, expect, it, vi } from 'vitest'

import { COURSES_INDEX_REDIRECT_SCRIPT } from './indexRedirect'

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

function run(pathname: string, storage: Record<string, string>, search = ''): string | null {
  let to: string | null = null
  vi.stubGlobal('localStorage', fakeStorage(storage))
  vi.stubGlobal('location', { pathname, search, replace: (url: string) => (to = url) })
  new Function(COURSES_INDEX_REDIRECT_SCRIPT)()
  return to
}

const session = JSON.stringify({ access_token: 'a', refresh_token: 'r' })

describe('courses index redirect', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('sends a signed-in student from the index to the home', () => {
    expect(run('/courses', { 'sb-abc-auth-token': session })).toBe('/')
    expect(run('/courses/', { 'sb-abc-auth-token': session })).toBe('/')
  })

  it('keeps a signed-in student on the catalog when they asked to explore all courses', () => {
    expect(run('/courses', { 'sb-abc-auth-token': session }, '?all=1')).toBeNull()
    expect(run('/courses', { 'sb-abc-auth-token': session }, '?x=1&all=1')).toBeNull()
    expect(run('/courses', { 'sb-abc-auth-token': session }, '?all=10')).toBe('/')
  })

  it('leaves the public catalog and the syllabus pages alone', () => {
    expect(run('/courses', {})).toBeNull()
    expect(run('/courses/cma', { 'sb-abc-auth-token': session })).toBeNull()
  })
})
