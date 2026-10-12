import { ALL_CHAPTERS_LABEL } from '~/modules/coverage'

/** "Taxation · GST: ITC", or "Taxation · All chapters" for a subject with no chapter; undefined without a subject. */
export function contextLabel(subjectName: string | undefined, chapterName: string | undefined): string | undefined {
  if (!subjectName) return chapterName
  return `${subjectName} · ${chapterName ?? ALL_CHAPTERS_LABEL}`
}
