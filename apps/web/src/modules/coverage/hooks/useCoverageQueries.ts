import { useQuery } from '@tanstack/react-query'

import { getChapter, getDue, getOverview, getSettings, getSubject, isNoEnrollment, listEnrollments } from '../lib/api'
import { coverageKeys } from '../lib/keys'

/** The active enrolment's overview. `data` is undefined and `noEnrollment` true when the student has not enrolled. */
export function useOverview() {
  const query = useQuery({
    queryKey: coverageKeys.overview,
    queryFn: getOverview,
    retry: (count, error) => !isNoEnrollment(error) && count < 1,
  })
  return { ...query, noEnrollment: isNoEnrollment(query.error) }
}

export const useEnrollments = () => useQuery({ queryKey: coverageKeys.enrollments, queryFn: listEnrollments })

export const useSubjectCoverage = (id: string) =>
  useQuery({ queryKey: coverageKeys.subject(id), queryFn: () => getSubject(id) })

export const useChapterCoverage = (id: string) =>
  useQuery({ queryKey: coverageKeys.chapter(id), queryFn: () => getChapter(id) })

export function useDue() {
  const query = useQuery({
    queryKey: coverageKeys.due,
    queryFn: getDue,
    retry: (count, error) => !isNoEnrollment(error) && count < 1,
  })
  return { ...query, noEnrollment: isNoEnrollment(query.error) }
}

export const useCoverageSettings = () => useQuery({ queryKey: coverageKeys.settings, queryFn: getSettings })
