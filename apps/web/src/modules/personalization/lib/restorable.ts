/**
 * Which pages are worth coming back to. A mirror of `apps/api/modules/profiles/domain/restorable.py`; both run the
 * same `restorable_cases.json`, so they cannot drift. The server stays the authority (it re-checks every write); the
 * web uses this to skip needless writes and to re-validate a value read back from the server or from localStorage.
 */
const MAX_PATH = 300
const MAX_SEARCH = 200
const SEGMENT = '[A-Za-z0-9_-]{1,64}'
const VALUE = /^[A-Za-z0-9_-]{1,32}$/

const ROUTES: ReadonlyArray<readonly [RegExp, ReadonlyArray<string>]> = [
  [/^\/app$/, []],
  [/^\/app\/syllabus$/, ['view', 'status']],
  [new RegExp(`^/app/syllabus/${SEGMENT}$`), []],
  [new RegExp(`^/app/syllabus/${SEGMENT}/${SEGMENT}$`), []],
  [/^\/app\/revision$/, []],
  [/^\/app\/tracker$/, []],
  [/^\/app\/tracker\/reports$/, ['range', 'by']],
  [/^\/app\/tracker\/log$/, []],
  [/^\/app\/tracker\/goals$/, []],
  [/^\/app\/focus$/, []],
  [/^\/app\/focus\/history$/, []],
]

export interface Visit {
  path: string
  search: string
}

function cleanSearch(search: string, keys: ReadonlyArray<string>): string {
  if (keys.length === 0 || !search || search.length > MAX_SEARCH) return ''
  const kept = new URLSearchParams()
  for (const [key, value] of new URLSearchParams(search.replace(/^\?/, ''))) {
    if (keys.includes(key) && VALUE.test(value)) kept.append(key, value)
  }
  return kept.toString()
}

/** The `{path, search}` to store, or null when the page is not restorable. */
export function cleanVisit(path: string, search = ''): Visit | null {
  if (!path || path.length > MAX_PATH || !path.startsWith('/')) return null
  const trimmed = path !== '/' && path.endsWith('/') ? path.replace(/\/+$/, '') : path
  for (const [pattern, keys] of ROUTES) {
    if (pattern.test(trimmed)) return { path: trimmed, search: cleanSearch(search, keys) }
  }
  return null
}

export const isRestorable = (target: string): boolean => {
  const [path = '', ...rest] = target.split('?')
  return cleanVisit(path, rest.join('?')) !== null
}

export const visitHref = (visit: Visit): string => (visit.search ? `${visit.path}?${visit.search}` : visit.path)
