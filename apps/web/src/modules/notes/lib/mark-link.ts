import type { ChapterSource } from './annotation-types'
import { effectiveLink } from './chapter-inheritance'
import type { PageRange } from './document-types'
import type { NoteLink } from './types'

/** A mark's chapter shown at once, before the server answers: the page's range, else the document's default (FR-F03-30). */
export function linkForPage(
  page: number,
  ranges: readonly PageRange[],
  documentLink: NoteLink,
): { link: NoteLink; source: ChapterSource } {
  const hit = effectiveLink<string>(
    page,
    null,
    ranges.map((r) => ({ page_from: r.page_from, page_to: r.page_to, chapter: r.chapter_id })),
    documentLink.chapter_id,
  )
  if (hit.source === 'range') {
    const r = ranges.find(
      (range) => range.chapter_id === hit.chapter && range.page_from <= page && page <= range.page_to,
    )
    if (r)
      return {
        source: 'range',
        link: {
          level_id: documentLink.level_id,
          subject_id: null,
          subject_key: r.subject_key,
          subject_name: r.subject_name,
          chapter_id: r.chapter_id,
          chapter_key: r.chapter_key,
          chapter_name: r.chapter_name,
          topic_id: r.topic_id,
          topic_key: r.topic_key,
          topic_name: r.topic_name,
          moved_or_removed: false,
        },
      }
  }
  if (hit.source === 'document') return { source: 'document', link: documentLink }
  return {
    source: 'none',
    link: documentLink.chapter_id
      ? documentLink
      : {
          ...documentLink,
          chapter_id: null,
          chapter_key: null,
          chapter_name: null,
          topic_id: null,
          topic_key: null,
          topic_name: null,
        },
  }
}
