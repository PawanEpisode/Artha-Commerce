import { useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'

import { PageRangeEditor } from '../components/library/PageRangeEditor'
import { useDocumentActions } from '../hooks/useLibrary'
import { useLevelId } from '../hooks/useNotesQueries'
import { suggestChapters } from '../lib/api'
import { linkFromSelection, type LinkSelection } from '../lib/chapter-link'
import type { DocumentDetail } from '../lib/document-types'
import { isRangesOverlap } from '../lib/errors'
import { notifyDocs } from '../lib/notify-documents'
import {
  emptyRow,
  mergeSuggestions,
  nextRowStart,
  overlapRows,
  type RangeRow,
  rowsFromOutlineSuggestions,
  rowsFromRanges,
  sameAsSaved,
  toRangeInputs,
  validateRows,
} from '../lib/page-ranges'
import { ChapterPicker } from './ChapterPicker'

const SUGGEST_LIMIT = 40
const SUGGEST_BATCH = 8

/** The page-range editor with its data: the rows, the chapter picker per row, outline suggestions, save and the 409. */
export function RangeEditorContainer({ doc }: { doc: DocumentDetail }) {
  const levelId = useLevelId()
  const actions = useDocumentActions()
  const qc = useQueryClient()
  const [rows, setRows] = useState<RangeRow[]>(() => rowsFromRanges(doc.ranges))
  const [serverProblems, setServerProblems] = useState<Record<string, string>>({})
  const [picking, setPicking] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const [suggesting, setSuggesting] = useState(false)
  const [note, setNote] = useState<string>()

  const problems = { ...validateRows(rows, doc.page_count), ...serverProblems }
  // Rows being typed show their mistake only once they hold something; an untouched new row stays calm.
  const visible = Object.fromEntries(
    Object.entries(problems).filter(([key]) => {
      const row = rows.find((r) => r.key === key)
      return row && (row.from !== '' || row.to !== '' || serverProblems[key])
    }),
  )
  const hasAny = Object.keys(problems).length > 0
  const dirty = !sameAsSaved(rows, doc.ranges)

  const edit = (key: string, change: Partial<RangeRow>) => {
    setServerProblems({})
    setRows((list) => list.map((r) => (r.key === key ? { ...r, ...change } : r)))
  }

  const suggest = async () => {
    const outline = doc.outline ?? []
    if (!doc.page_count || outline.length === 0) {
      setNote('This PDF has no contents list to start from. Add ranges by hand.')
      return
    }
    setSuggesting(true)
    setNote(undefined)
    const suggestions = rowsFromOutlineSuggestions(outline, doc.page_count).slice(0, SUGGEST_LIMIT)
    for (let i = 0; i < suggestions.length; i += SUGGEST_BATCH) {
      await Promise.all(
        suggestions.slice(i, i + SUGGEST_BATCH).map(async (row) => {
          const [best] = await suggestChapters(row.title, levelId).catch(() => [])
          if (best) {
            row.chapterId = best.chapter_id
            row.chapterLabel = `${best.subject_name} › ${best.chapter_name}`
          }
        }),
      )
    }
    setRows((list) => mergeSuggestions(list, suggestions))
    setSuggesting(false)
    setNote('Suggested from the contents of the PDF. Check each chapter before saving.')
  }

  const save = async () => {
    setSaving(true)
    const { inputs, order } = toRangeInputs(rows)
    try {
      const result = await actions.saveRanges(doc.id, inputs)
      setRows(rowsFromRanges(result.ranges))
      notifyDocs.rangesSaved(result.relinked)
      void qc.invalidateQueries({ queryKey: ['notes', 'document', doc.id], exact: true })
    } catch (error) {
      if (isRangesOverlap(error)) setServerProblems(overlapRows(error, order))
      else notifyDocs.error(error, 'Could not save the page ranges.')
    } finally {
      setSaving(false)
    }
  }

  const pickingRow = rows.find((r) => r.key === picking)
  const onSelect = (selection: LinkSelection | null) => {
    if (!picking || !selection) return
    edit(picking, {
      chapterId: selection.chapterId,
      chapterLabel: `${selection.subjectName} › ${selection.chapterName}`,
      topicId: selection.topicId,
      source: 'user',
    })
    setPicking(null)
  }

  return (
    <>
      <PageRangeEditor
        rows={rows}
        problems={visible}
        pageCount={doc.page_count}
        onEdit={(key, change) => edit(key, change)}
        onAdd={() => setRows((list) => [...list, emptyRow(nextRowStart(list, doc.page_count))])}
        onRemove={(key) => {
          setServerProblems({})
          setRows((list) => list.filter((r) => r.key !== key))
        }}
        onPickChapter={setPicking}
        onSuggest={() => void suggest()}
        suggesting={suggesting}
        dirty={dirty}
        saving={saving}
        onSave={() => void save()}
        onReset={() => {
          setServerProblems({})
          setRows(rowsFromRanges(doc.ranges))
        }}
      />
      {note ? (
        <p role="status" className="text-sm text-muted-foreground">
          {note}
        </p>
      ) : null}
      {hasAny && dirty && Object.keys(visible).length === 0 ? (
        <p className="text-sm text-muted-foreground">Fill in every row (pages and chapter) to save.</p>
      ) : null}
      {pickingRow ? (
        <ChapterPicker
          link={linkFromSelection(null)}
          showTrigger={false}
          open
          onOpenChange={(open) => !open && setPicking(null)}
          onSelect={onSelect}
        />
      ) : null}
    </>
  )
}
