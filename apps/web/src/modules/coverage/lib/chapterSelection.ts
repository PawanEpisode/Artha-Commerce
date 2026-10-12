import { ALL_CHAPTERS } from './subjects'

/** A chapter choice next to a Subject field: one chapter, "All chapters" (the whole subject), or nothing yet. */
export interface ChapterSelection {
  chapter_id: string | null
  /** "All chapters" was chosen: the whole subject, so no chapter id is sent. */
  all_chapters: boolean
}

/** The select value for a choice: the chapter id, `ALL_CHAPTERS`, or '' while nothing is chosen. */
export const chapterSelectValue = (s: ChapterSelection): string =>
  s.all_chapters ? ALL_CHAPTERS : (s.chapter_id ?? '')

/** What a select value means: `ALL_CHAPTERS` is the whole subject, '' is unset, anything else a chapter id. */
export function chapterSelectionOf(value: string): ChapterSelection {
  const all = value === ALL_CHAPTERS
  return { chapter_id: value && !all ? value : null, all_chapters: all }
}

export const isChapterUnset = (s: ChapterSelection): boolean => !s.all_chapters && !s.chapter_id

/**
 * How a stored record (a running timer, a logged session) reads back: a subject with no chapter is the whole subject,
 * so it shows "All chapters" rather than a blank.
 */
export function storedChapterSelection(subjectId: string | null, chapterId: string | null): ChapterSelection {
  return { chapter_id: chapterId, all_chapters: Boolean(subjectId) && !chapterId }
}
