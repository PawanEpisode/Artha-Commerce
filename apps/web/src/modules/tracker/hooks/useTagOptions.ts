import { useOverview, useSubjectCoverage } from '~/modules/coverage'

type Overview = NonNullable<ReturnType<typeof useOverview>['data']>

/** Core papers plus only the elective papers the student chose (the others are not on their syllabus). */
function chosenSubjects(data: Overview | undefined) {
  const chosen = new Map((data?.electives ?? []).map((slot) => [slot.key, slot.chosen]))
  return (data?.subjects ?? []).filter((s) => !s.elective_slot || chosen.get(s.elective_slot) === s.id)
}

/** Subjects of the student's enrolment, for the pickers, with whether they are still loading. */
export function useSubjectOptionsState() {
  const { data, isPending } = useOverview()
  return {
    options: chosenSubjects(data).map((s) => ({ id: s.id, name: s.name, key: s.key })),
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
