import { Button, type ButtonProps, StickyNote } from '@artha/design-system'
import { useNavigate } from '@tanstack/react-router'
import { useRef, useState } from 'react'

import { useFeatureFlag } from '~/modules/observability'

import { useNoteActions } from '../hooks/useNoteActions'
import { useNotesFlusher } from '../hooks/useNotesSync'
import { notesAnalytics } from '../lib/analytics'
import { newClientId } from '../lib/api'
import { notify } from '../lib/notify'
import type { ClipSource } from '../lib/types'

export interface SaveToNotesProps extends Pick<ButtonProps, 'variant' | 'size' | 'className'> {
  /** The Markdown to keep (a highlighted passage, an explanation). Empty text disables the button. */
  text: string
  /** Where it came from, so the note says so: `{module: 'syllabus', ref: 'chapter-key', label: 'GST: ITC'}`. */
  source: ClipSource
  /** File it under this chapter (and topic) right away. Both are ids from the F-02 syllabus. */
  chapterId?: string | null
  topicId?: string | null
  label?: string
}

/**
 * "Save to notes" for any module. Creates a note from `text` with a client id, so a double tap or a replay after
 * going offline never makes two. Works offline (it waits in the notes queue) and is hidden when the flag is off.
 */
export function SaveToNotes({
  text,
  source,
  chapterId,
  topicId,
  label = 'Save to notes',
  ...button
}: SaveToNotesProps) {
  const enabled = useFeatureFlag('notes')
  const navigate = useNavigate()
  const actions = useNoteActions()
  useNotesFlusher(enabled)
  const [busy, setBusy] = useState(false)
  const id = useRef({ key: '', clientId: newClientId() })

  if (!enabled) return null

  const save = async () => {
    const key = `${source.module}|${source.ref}|${text}`
    if (id.current.key !== key) id.current = { key, clientId: newClientId() }
    setBusy(true)
    try {
      const result = await actions.clip({
        client_id: id.current.clientId,
        text_md: text,
        source,
        chapter_id: chapterId ?? null,
        topic_id: topicId ?? null,
      })
      if (result.status === 'queued') {
        notify.clipQueued()
      } else {
        const note = result.data.note
        notify.clipSaved(() => void navigate({ to: '/app/notes/n/$noteId', params: { noteId: note.id } }))
        if (result.data.created) {
          notesAnalytics.noteCreated({ source: 'clip', hasChapter: Boolean(chapterId), first: false })
          if (chapterId) notesAnalytics.itemLinked('clip')
        }
      }
    } catch (error) {
      if (!actions.handleQuota(error)) notify.error(error, 'Could not save to notes.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <Button variant="outline" {...button} disabled={busy || text.trim() === ''} onClick={() => void save()}>
      <StickyNote aria-hidden /> {label}
    </Button>
  )
}
