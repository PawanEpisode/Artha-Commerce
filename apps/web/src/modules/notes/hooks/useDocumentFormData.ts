import { useMemo } from 'react'

import type { PickerState } from '../lib/chapter-link'
import { selectionOfDraft } from '../lib/document-draft'
import { useChapterPickerData } from './useChapterPickerData'
import { useLevelId } from './useNotesQueries'

/**
 * The syllabus lists behind the Filing step and the finished selection they make: null for Unfiled, undefined while a list
 * the choice needs is still loading, otherwise a chapter or subject-level (All chapters) selection ready to send.
 */
export function useDocumentFormData(filing: PickerState) {
  const levelId = useLevelId()
  const data = useChapterPickerData(filing)
  const selection = useMemo(
    () => selectionOfDraft(levelId, filing, data.subjects, data.chapters, data.topics),
    [levelId, filing, data.subjects, data.chapters, data.topics],
  )
  return { data, selection, levelId }
}

export type DocumentFormData = ReturnType<typeof useDocumentFormData>
