import { useOverview, useSubjectCoverage } from '~/modules/coverage'

/** Subjects of the student's enrolment, for the pickers. Empty (so "No subject" only) until they enrol. */
export function useSubjectOptions() {
  const { data } = useOverview()
  return data?.subjects.map((s) => ({ id: s.id, name: s.name, key: s.key })) ?? []
}

export function useChapterOptions(subjectId: string | null) {
  const q = useSubjectCoverage(subjectId ?? '', !!subjectId)
  return q.data?.chapters.map((c) => ({ id: c.id, name: c.name, key: c.key })) ?? []
}
