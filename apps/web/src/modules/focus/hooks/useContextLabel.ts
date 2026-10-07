import { useChapterOptions, useSubjectOptions } from '~/modules/tracker'

/** "Taxation · GST: ITC": the subject and chapter names for an id pair, or undefined when neither is known. */
export function useContextLabel(subjectId: string | null, chapterId: string | null): string | undefined {
  const subjects = useSubjectOptions()
  const chapters = useChapterOptions(subjectId)
  const parts = [subjects.find((s) => s.id === subjectId)?.name, chapters.find((c) => c.id === chapterId)?.name]
  const label = parts.filter(Boolean).join(' · ')
  return label || undefined
}
