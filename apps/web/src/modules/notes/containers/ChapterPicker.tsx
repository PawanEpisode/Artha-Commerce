import { useEffect, useState } from 'react'

import { ChapterPickerSheet } from '../components/ChapterPickerSheet'
import { useChapterPickerData } from '../hooks/useChapterPickerData'
import {
  buildSelection,
  linkFromSelection,
  linkLabel,
  type LinkSelection,
  pickerReduce,
  type PickerState,
  selectionFromLink,
} from '../lib/chapter-link'
import type { NoteLink } from '../lib/types'

const EMPTY: PickerState = { subjectId: '', chapterId: '', topicId: '' }

interface ChapterPickerProps {
  /** What the note is filed under now. */
  link: NoteLink
  /** The student's choice, when the picker is used before a note exists (new note). */
  selection?: LinkSelection | null
  onSelect: (selection: LinkSelection | null) => void
  open?: boolean
  onOpenChange?: (open: boolean) => void
  disabled?: boolean
  showTrigger?: boolean
}

/** Container of the F-02 picker: reads the syllabus lists, keeps the three choices, and hands back a stable-key selection. */
export function ChapterPicker({
  link,
  selection,
  onSelect,
  open: controlled,
  onOpenChange,
  disabled,
  showTrigger,
}: ChapterPickerProps) {
  const [inner, setInner] = useState(false)
  const open = controlled ?? inner
  const setOpen = onOpenChange ?? setInner
  const current = selection ?? selectionFromLink(link)
  const [state, setState] = useState<PickerState>(EMPTY)
  const data = useChapterPickerData(state)

  // Start from where the note is filed each time the sheet opens. The ids come from the loaded subject list.
  useEffect(() => {
    if (!open) return
    const subjectId = data.subjects.find((s) => s.key === current?.subjectKey)?.id ?? current?.subjectId ?? ''
    setState({ subjectId, chapterId: current?.chapterId ?? '', topicId: current?.topicId ?? '' })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, data.subjects.length])

  const built =
    data.levelId !== undefined ? buildSelection(data.levelId, state, data.subjects, data.chapters, data.topics) : null

  return (
    <ChapterPickerSheet
      currentLabel={
        selection === undefined ? linkLabel(link) : selection ? linkLabel(linkFromSelection(selection)) : 'Unfiled'
      }
      open={open}
      onOpenChange={setOpen}
      state={state}
      onState={(change) => setState((s) => pickerReduce(s, change))}
      subjects={data.subjects}
      chapters={data.chapters}
      topics={data.topics}
      loadingSubjects={data.loadingSubjects}
      loadingChapters={data.loadingChapters}
      loadingTopics={data.loadingTopics}
      failed={data.failed}
      onRetry={data.retry}
      canApply={built !== null}
      onApply={() => {
        if (!built) return
        onSelect(built)
        setOpen(false)
      }}
      onClear={
        current
          ? () => {
              onSelect(null)
              setOpen(false)
            }
          : undefined
      }
      disabled={disabled}
      showTrigger={showTrigger}
    />
  )
}
