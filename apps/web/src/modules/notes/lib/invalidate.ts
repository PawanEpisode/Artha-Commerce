import type { QueryClient } from '@tanstack/react-query'

import { notesKeys } from './keys'

/**
 * After a note's chapter/topic changes: refresh the lists that show it, the subject counts that
 * moved, and any open chapter overview. Does not touch usage or tags.
 */
export function invalidateAfterNoteLink(
  qc: QueryClient,
  subjects: Iterable<string | null | undefined>,
): Promise<unknown> {
  const keys = new Set<string>()
  for (const subject of subjects) {
    if (subject) keys.add(subject)
  }
  const jobs: Promise<unknown>[] = [
    qc.invalidateQueries({ queryKey: notesKeys.lists }),
    qc.invalidateQueries({ queryKey: notesKeys.aggregates }),
    qc.invalidateQueries({ queryKey: notesKeys.overviews }),
  ]
  if (keys.size === 0) {
    jobs.push(qc.invalidateQueries({ queryKey: notesKeys.allCounts }))
  } else {
    for (const subject of keys) {
      jobs.push(qc.invalidateQueries({ queryKey: notesKeys.counts(subject) }))
    }
  }
  return Promise.all(jobs)
}
