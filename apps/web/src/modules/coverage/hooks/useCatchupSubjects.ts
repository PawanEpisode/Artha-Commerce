import { useQueries } from '@tanstack/react-query'
import { useMemo } from 'react'

import type { CatchupSubject } from '../components/CatchupStep'
import { getSubject } from '../lib/api'
import { coverageKeys } from '../lib/keys'
import { useOverview } from './useCoverageQueries'

/**
 * The papers and chapters the quick catch-up lists, for the student's active enrolment. Papers of an elective the
 * student did not choose are left out (they are not on their syllabus). One request per paper, cached.
 */
export function useCatchupSubjects(enabled = true) {
  const overview = useOverview(enabled)
  const ov = overview.data

  const subjects = useMemo(() => {
    const chosen = new Map((ov?.electives ?? []).map((slot) => [slot.key, slot.chosen]))
    return (ov?.subjects ?? []).filter((s) => !s.elective_slot || chosen.get(s.elective_slot) === s.id)
  }, [ov])

  const chapterQueries = useQueries({
    queries: subjects.map((s) => ({
      queryKey: coverageKeys.subject(s.id),
      queryFn: () => getSubject(s.id),
      enabled,
    })),
  })

  const catchupSubjects = useMemo<CatchupSubject[]>(
    () => subjects.map((subject, i) => ({ subject, chapters: chapterQueries[i]?.data?.chapters })),
    [subjects, chapterQueries],
  )

  return {
    overview: ov,
    subjects: catchupSubjects,
    hiddenElectives: (ov?.subjects.length ?? 0) > subjects.length,
    loading: overview.isPending || chapterQueries.some((q) => q.isPending),
    failed: overview.isError || chapterQueries.some((q) => q.isError),
    noEnrollment: overview.noEnrollment,
  }
}
