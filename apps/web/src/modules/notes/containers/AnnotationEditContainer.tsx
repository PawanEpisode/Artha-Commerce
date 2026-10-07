import { Button } from '@artha/design-system'
import { useEffect, useMemo, useRef, useState } from 'react'

import { AnnotationEditSheet } from '../components/annotations/AnnotationEditSheet'
import { TagEditor } from '../components/TagEditor'
import { useNoteActions } from '../hooks/useNoteActions'
import { useTags } from '../hooks/useNotesQueries'
import { inkOptions } from '../lib/annotation-legend'
import { linkFromSelection, linkLabel } from '../lib/chapter-link'
import { markHeading } from '../lib/mark-label'
import { useUiScope } from './annotation-scope'
import { ChapterPicker } from './ChapterPicker'

const COMMIT_MS = 600

const SOURCE_TEXT = {
  explicit: 'Set by you',
  range: 'From this page range',
  document: 'From the PDF',
  none: '',
} as const

/**
 * The edit sheet of one mark. The comment is kept in a local draft and saved 600 ms after the last key and on close, so
 * typing never sends a request per letter; colour, tags and chapter save at once. An empty new pin is discarded on close.
 */
export function AnnotationEditContainer() {
  const ui = useUiScope()
  const tags = useTags()
  const actions = useNoteActions()
  const mark = ui?.edit ? ui.marks.find(ui.edit.id) : undefined
  const [draft, setDraft] = useState<{ id: string; text: string } | null>(null)
  const [pickerOpen, setPickerOpen] = useState(false)
  const field = useRef<HTMLTextAreaElement | null>(null)
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const latest = useRef({ ui, mark, draft })
  latest.current = { ui, mark, draft }

  const flush = () => {
    if (timer.current) clearTimeout(timer.current)
    timer.current = null
    const { ui: scope, mark: current, draft: pending } = latest.current
    if (scope && current && pending?.id === current.id && pending.text !== current.comment)
      scope.marks.edit(current.id, { comment: pending.text })
  }

  const editId = ui?.edit?.id
  useEffect(() => {
    setDraft(null)
    setPickerOpen(false)
  }, [editId])
  useEffect(() => () => flush(), [])

  const colorOptions = useMemo(() => {
    if (!ui || !mark) return []
    if (mark.kind === 'bookmark') return []
    return mark.kind === 'ink' || mark.kind === 'textbox' ? inkOptions() : ui.settings.options
  }, [ui, mark])

  if (!ui || !ui.edit || !mark) return null
  const text = draft?.id === mark.id ? draft.text : mark.comment
  const offline = !ui.marks.online
  const close = () => {
    flush()
    const empty = (draft?.id === mark.id ? draft.text : mark.comment).trim() === ''
    if (ui.edit?.fresh && mark.kind === 'sticky' && empty) ui.marks.remove(mark.id, { silent: true })
    ui.closeEdit()
  }
  const chapterText = linkLabel(mark.link)
  const source = SOURCE_TEXT[mark.chapter_source]

  return (
    <AnnotationEditSheet
      open
      onOpenChange={(next) => !next && close()}
      kind={mark.kind}
      heading={markHeading(mark)}
      quote={mark.kind === 'highlight' || mark.kind === 'underline' ? (mark.quote_exact ?? undefined) : undefined}
      color={mark.color}
      colorOptions={colorOptions}
      colorLabel={mark.kind === 'ink' || mark.kind === 'textbox' ? 'Pen colour' : 'Colour'}
      onColor={(key) => ui.marks.edit(mark.id, { color: key })}
      comment={text}
      onCommentChange={(next) => {
        setDraft({ id: mark.id, text: next })
        if (timer.current) clearTimeout(timer.current)
        timer.current = setTimeout(flush, COMMIT_MS)
      }}
      commentRef={ui.edit.focusComment ? field : undefined}
      tags={
        <TagEditor
          tags={tags.data ?? []}
          selectedIds={mark.tags.map((t) => t.id)}
          onChange={(ids) =>
            ui.marks.edit(
              mark.id,
              { tag_ids: ids },
              {
                tags: (tags.data ?? [])
                  .filter((t) => ids.includes(t.id))
                  .map((t) => ({ id: t.id, name: t.name, color_key: t.color_key })),
              },
            )
          }
          onCreate={actions.addTag}
          createDisabledReason={offline ? 'Making a tag needs a connection.' : undefined}
        />
      }
      chapter={
        <div className="space-y-2">
          <p className="text-sm">
            {chapterText}
            {source ? <span className="text-muted-foreground"> ({source})</span> : null}
          </p>
          <div className="flex flex-wrap gap-2">
            <ChapterPicker
              link={mark.link}
              open={pickerOpen}
              onOpenChange={setPickerOpen}
              showTrigger
              onSelect={(selection) => {
                if (selection)
                  ui.marks.edit(
                    mark.id,
                    { chapter_id: selection.chapterId, topic_id: selection.topicId },
                    { link: linkFromSelection(selection) },
                  )
                else ui.marks.edit(mark.id, { chapter_id: null, topic_id: null })
              }}
            />
            {mark.chapter_source === 'explicit' ? (
              <Button
                variant="ghost"
                className="min-h-11"
                onClick={() => ui.marks.edit(mark.id, { chapter_id: null, topic_id: null })}
              >
                Use the page&rsquo;s chapter
              </Button>
            ) : null}
          </div>
        </div>
      }
      canCard={ui.settings.canCard}
      cardDisabledReason={offline ? 'Cards need a connection.' : undefined}
      hasCard={mark.recall_card_id !== null}
      onCard={() => void ui.marks.makeCard(mark.id)}
      onDelete={() => {
        flush()
        ui.closeEdit()
        ui.marks.remove(mark.id)
      }}
    />
  )
}
