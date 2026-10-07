import { useState } from 'react'

import { SuggestionBar } from '../components/SuggestionBar'
import { useNoteActions } from '../hooks/useNoteActions'
import { useChapterSuggestions, useLevelId } from '../hooks/useNotesQueries'
import { notesAnalytics } from '../lib/analytics'
import { selectionFromSuggestion } from '../lib/chapter-link'
import type { NoteSummary } from '../lib/types'
import { ChapterPicker } from './ChapterPicker'

/** Under an unfiled note: up to three one-tap chapter suggestions from the server's text match, and the full picker. */
export function UnfiledRow({ note }: { note: NoteSummary }) {
  const levelId = useLevelId()
  const actions = useNoteActions()
  const [open, setOpen] = useState(false)
  const [busy, setBusy] = useState(false)
  const suggestions = useChapterSuggestions(note.id, `${note.title}\n${note.snippet}`, true)

  return (
    <>
      <SuggestionBar
        suggestions={suggestions.data ?? []}
        busy={busy}
        onPick={async (suggestion) => {
          if (!levelId) return
          setBusy(true)
          const done = await actions.change(note, { selection: selectionFromSuggestion(suggestion, levelId) })
          setBusy(false)
          if (done) notesAnalytics.itemLinked('suggestion')
        }}
        onOther={() => setOpen(true)}
      />
      <ChapterPicker
        link={note.link}
        showTrigger={false}
        open={open}
        onOpenChange={setOpen}
        onSelect={async (selection) => {
          if (!selection) return
          const done = await actions.change(note, { selection })
          if (done) notesAnalytics.itemLinked('manual')
        }}
      />
    </>
  )
}
