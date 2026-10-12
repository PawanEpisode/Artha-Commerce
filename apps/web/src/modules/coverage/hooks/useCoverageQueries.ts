import { useQuery } from '@tanstack/react-query'
import { useMemo } from 'react'

import {
  getChapter,
  getContinue,
  getDue,
  getOverview,
  getSettings,
  getSubject,
  isFeatureDisabled,
  isNoEnrollment,
  listEnrollments,
} from '../lib/api'
import { coverageKeys } from '../lib/keys'
import { chosenSubjects } from '../lib/subjects'

/**
 * The active enrolment's overview. `data` is undefined and `noEnrollment` true when the student has not enrolled.
 * Pass `enabled: false` on public pages until the student is signed in, so guests never hit the authed endpoint.
 */
export function useOverview(enabled = true) {
  const query = useQuery({
    queryKey: coverageKeys.overview,
    queryFn: getOverview,
    enabled,
  })
  return { ...query, noEnrollment: isNoEnrollment(query.error), featureDisabled: isFeatureDisabled(query.error) }
}

/** The papers on the student's syllabus: core papers and the chosen electives only (never the electives they skipped). */
export function useChosenSubjects() {
  const query = useOverview()
  return { ...query, subjects: useMemo(() => chosenSubjects(query.data), [query.data]) }
}

export const useEnrollments = () => useQuery({ queryKey: coverageKeys.enrollments, queryFn: listEnrollments })

export const useSubjectCoverage = (id: string, enabled = true) =>
  useQuery({ queryKey: coverageKeys.subject(id), queryFn: () => getSubject(id), enabled: enabled && id !== '' })

export const useChapterCoverage = (id: string, enabled = id !== '') =>
  useQuery({ queryKey: coverageKeys.chapter(id), queryFn: () => getChapter(id), enabled })

export function useDue() {
  const query = useQuery({
    queryKey: coverageKeys.due,
    queryFn: getDue,
  })
  return { ...query, noEnrollment: isNoEnrollment(query.error) }
}

/** The most recently studied chapter (null before the first activity). Same failure rules as the overview. */
export function useContinue() {
  const query = useQuery({
    queryKey: coverageKeys.continue,
    queryFn: getContinue,
  })
  return { ...query, noEnrollment: isNoEnrollment(query.error), featureDisabled: isFeatureDisabled(query.error) }
}

export const useCoverageSettings = () => useQuery({ queryKey: coverageKeys.settings, queryFn: getSettings })
