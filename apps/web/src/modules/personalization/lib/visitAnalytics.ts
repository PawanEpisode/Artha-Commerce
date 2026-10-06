import { ageBucket } from '~/modules/observability'

import type { StoredVisit } from './lastVisit'

/** The section of a restorable page: "syllabus", "tracker", "focus"... never an id. */
export function pathKind(path: string): string {
  const [, app, section] = path.split('/')
  return app === 'app' ? section || 'home' : 'other'
}

export interface RestoreEvent {
  path_kind: string
  age_bucket: ReturnType<typeof ageBucket>
  source: 'server' | 'local'
}

interface Winner {
  path: string
  search: string
  at: string | null
}

/**
 * `last_visit_restored` (PRD 10), or null when the destination was not the last visit (a deep link, onboarding or the
 * default home won). `source` says which copy won: the server's, or the newer one kept on this device.
 */
export function restoreEvent(
  destination: string,
  visit: Winner | null,
  local: StoredVisit | null,
  now: Date = new Date(),
): RestoreEvent | null {
  if (!visit?.at) return null
  const target = visit.search ? `${visit.path}?${visit.search}` : visit.path
  if (destination !== target) return null
  return {
    path_kind: pathKind(visit.path),
    age_bucket: ageBucket(now.getTime() - Date.parse(visit.at)),
    source: visit === local ? 'local' : 'server',
  }
}
