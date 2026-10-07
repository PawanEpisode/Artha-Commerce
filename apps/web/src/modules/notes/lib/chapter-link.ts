import type { ChapterOverview, ChapterSuggestion, NoteLink } from './types'

/** A student's choice in the picker: stable keys next to the ids the API writes (FR-F03-40). */
export interface LinkSelection {
  levelId: string
  subjectId: string
  subjectKey: string
  subjectName: string
  chapterId: string
  chapterKey: string
  chapterName: string
  topicId: string | null
  topicKey: string | null
  topicName: string | null
}

export const isUnfiled = (link: Pick<NoteLink, 'chapter_id' | 'chapter_key'>) =>
  link.chapter_id === null && link.chapter_key === null

/** "Taxation › GST: ITC › Section 17(5)", or "Unfiled". */
export function linkLabel(link: NoteLink): string {
  if (isUnfiled(link)) return 'Unfiled'
  return [link.subject_name, link.chapter_name, link.topic_name].filter(Boolean).join(' › ')
}

/** Just the chapter, for a compact chip; falls back to the subject, then to "Unfiled". */
export const shortLinkLabel = (link: NoteLink) => link.chapter_name ?? link.subject_name ?? 'Unfiled'

/** What to send so a note ends up linked (or unfiled with `null`). Topic only counts inside a chapter. */
export function linkFields(selection: LinkSelection | null): { chapter_id: string | null; topic_id: string | null } {
  if (!selection) return { chapter_id: null, topic_id: null }
  return { chapter_id: selection.chapterId, topic_id: selection.topicId }
}

export function selectionFromLink(link: NoteLink): LinkSelection | null {
  if (!link.level_id || !link.subject_id || !link.subject_key || !link.chapter_id || !link.chapter_key) return null
  return {
    levelId: link.level_id,
    subjectId: link.subject_id,
    subjectKey: link.subject_key,
    subjectName: link.subject_name ?? '',
    chapterId: link.chapter_id,
    chapterKey: link.chapter_key,
    chapterName: link.chapter_name ?? '',
    topicId: link.topic_id,
    topicKey: link.topic_key,
    topicName: link.topic_name,
  }
}

export function selectionFromOverview(
  overview: ChapterOverview,
  topic?: { id: string; key: string; name: string },
): LinkSelection {
  const { chapter } = overview
  return {
    levelId: chapter.level_id,
    subjectId: '',
    subjectKey: chapter.subject_key,
    subjectName: chapter.subject_name,
    chapterId: chapter.id,
    chapterKey: chapter.key,
    chapterName: chapter.name,
    topicId: topic?.id ?? null,
    topicKey: topic?.key ?? null,
    topicName: topic?.name ?? null,
  }
}

export function selectionFromSuggestion(suggestion: ChapterSuggestion, levelId: string): LinkSelection {
  return {
    levelId,
    subjectId: suggestion.subject_id,
    subjectKey: suggestion.subject_key,
    subjectName: suggestion.subject_name,
    chapterId: suggestion.chapter_id,
    chapterKey: suggestion.chapter_key,
    chapterName: suggestion.chapter_name,
    topicId: null,
    topicKey: null,
    topicName: null,
  }
}

export interface PickerOption {
  id: string
  key: string
  name: string
}

export interface PickerState {
  subjectId: string
  chapterId: string
  topicId: string
}

/** Changing the subject clears the chapter and topic; changing the chapter clears the topic. */
export function pickerReduce(state: PickerState, change: Partial<PickerState>): PickerState {
  if ('subjectId' in change && change.subjectId !== state.subjectId) {
    return { subjectId: change.subjectId ?? '', chapterId: '', topicId: '' }
  }
  if ('chapterId' in change && change.chapterId !== state.chapterId) {
    return { ...state, chapterId: change.chapterId ?? '', topicId: '' }
  }
  return { ...state, ...change }
}

/** The finished selection from the picker's lists, or null while no chapter is chosen. */
export function buildSelection(
  levelId: string,
  state: PickerState,
  subjects: PickerOption[],
  chapters: PickerOption[],
  topics: PickerOption[],
): LinkSelection | null {
  const subject = subjects.find((s) => s.id === state.subjectId)
  const chapter = chapters.find((c) => c.id === state.chapterId)
  if (!subject || !chapter) return null
  const topic = topics.find((t) => t.id === state.topicId)
  return {
    levelId,
    subjectId: subject.id,
    subjectKey: subject.key,
    subjectName: subject.name,
    chapterId: chapter.id,
    chapterKey: chapter.key,
    chapterName: chapter.name,
    topicId: topic?.id ?? null,
    topicKey: topic?.key ?? null,
    topicName: topic?.name ?? null,
  }
}

/** Does a selection differ from what the note already has? (No write for a no-op.) */
export function sameLink(selection: LinkSelection | null, link: NoteLink): boolean {
  if (!selection) return isUnfiled(link)
  return selection.chapterId === link.chapter_id && (selection.topicId ?? null) === (link.topic_id ?? null)
}

/** The `link` a note shows after the student picks (or clears) a chapter, before the server answers. */
export function linkFromSelection(selection: LinkSelection | null): NoteLink {
  if (!selection) {
    return {
      level_id: null,
      subject_id: null,
      subject_key: null,
      subject_name: null,
      chapter_id: null,
      chapter_key: null,
      chapter_name: null,
      topic_id: null,
      topic_key: null,
      topic_name: null,
      moved_or_removed: false,
    }
  }
  return {
    level_id: selection.levelId,
    subject_id: selection.subjectId || null,
    subject_key: selection.subjectKey,
    subject_name: selection.subjectName,
    chapter_id: selection.chapterId,
    chapter_key: selection.chapterKey,
    chapter_name: selection.chapterName,
    topic_id: selection.topicId,
    topic_key: selection.topicKey,
    topic_name: selection.topicName,
    moved_or_removed: false,
  }
}
