import { contextLabel, useChapterOptions, useSubjectOptions } from '~/modules/tracker'

/** "Taxation · GST: ITC" for an id pair; "Taxation · All chapters" with no chapter; undefined when no subject is known. */
export function useContextLabel(subjectId: string | null, chapterId: string | null): string | undefined {
  const subjects = useSubjectOptions()
  const chapters = useChapterOptions(subjectId)
  return contextLabel(subjects.find((s) => s.id === subjectId)?.name, chapters.find((c) => c.id === chapterId)?.name)
}
