import { useCallback, useState } from 'react'

import { notesAnalytics } from '../lib/analytics'
import { listNotes } from '../lib/api'
import type { LinkSelection } from '../lib/chapter-link'
import { notify } from '../lib/notify'
import type { NoteSummary } from '../lib/types'
import { useNoteActions } from './useNoteActions'

/**
 * Re-files every note of a chapter that is no longer in the syllabus under a chapter that exists now. The notes are
 * collected first (their order changes as they move), then each is filed with the same queue-aware write.
 */
export function useRelink() {
  const actions = useNoteActions()
  const [busy, setBusy] = useState(false)

  const relink = useCallback(
    async (levelId: string, subjectKey: string, chapterKey: string, selection: LinkSelection) => {
      setBusy(true)
      try {
        const notes: NoteSummary[] = []
        let cursor: string | undefined
        do {
          const page = await listNotes({ level: levelId, subject: subjectKey, chapter: chapterKey, limit: 100, cursor })
          notes.push(...page.items)
          cursor = page.next_cursor ?? undefined
        } while (cursor)
        for (const note of notes) {
          await actions.change(note, { selection })
          notesAnalytics.itemLinked('manual')
        }
        notify.filed(selection.chapterName)
        return notes.length
      } catch (error) {
        notify.error(error, 'Could not re-link these notes.')
        return 0
      } finally {
        setBusy(false)
      }
    },
    [actions],
  )

  return { relink, busy }
}
