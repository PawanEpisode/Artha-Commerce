import { useOverview, useSubjectCoverage } from '~/modules/coverage'

/** Subjects of the student's enrolment, for the pickers, with whether they are still loading. */
export function useSubjectOptionsState() {
  const { data, isPending } = useOverview()
  return {
    options: data?.subjects.map((s) => ({ id: s.id, name: s.name, key: s.key })) ?? [],
    loading: isPending,
  }
}

/** Chapters of one subject, with whether they are loading (false while no subject is chosen: nothing is being fetched). */
export function useChapterOptionsState(subjectId: string | null) {
  const q = useSubjectCoverage(subjectId ?? '', !!subjectId)
  return {
    options: q.data?.chapters.map((c) => ({ id: c.id, name: c.name, key: c.key })) ?? [],
    loading: !!subjectId && q.isPending,
  }
}

/** Subjects of the student's enrolment, for the pickers. Empty (so "No subject" only) until they enrol. */
export const useSubjectOptions = () => useSubjectOptionsState().options

export const useChapterOptions = (subjectId: string | null) => useChapterOptionsState(subjectId).options
