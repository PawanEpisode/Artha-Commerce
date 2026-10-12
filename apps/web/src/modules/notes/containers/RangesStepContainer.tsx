import { useState } from 'react'

import { ChapterFields } from '../components/ChapterFields'
import { PageRangeEditor } from '../components/library/PageRangeEditor'
import { useChapterPickerData } from '../hooks/useChapterPickerData'
import { useEnrolledSubjects, useLevelId } from '../hooks/useNotesQueries'
import { suggestChapters } from '../lib/api'
import type { OutlineNode } from '../lib/chapter-inheritance'
import { pickerReduce, type PickerState } from '../lib/chapter-link'
import {
  emptyRow,
  filledRows,
  mergeSuggestions,
  nextRowStart,
  type RangeRow,
  type RowProblems,
  rowsFromOutlineSuggestions,
  validateRows,
} from '../lib/page-ranges'

const SUGGEST_LIMIT = 40
const SUGGEST_BATCH = 8

/** The subject and chapter fields of one range row: the student's own papers, then that paper's chapters. No "All chapters". */
function RangeRowChapter({ row, onChange }: { row: RangeRow; onChange: (change: Partial<RangeRow>) => void }) {
  const { subjects } = useEnrolledSubjects()
  const subjectId = row.subjectId || subjects.find((s) => s.key === row.subjectKey)?.id || ''
  const state: PickerState = { subjectId, chapterId: row.chapterId, topicId: '' }
  const data = useChapterPickerData(state, { topics: false })
  return (
    <div className="space-y-2">
      <ChapterFields
        idPrefix={`range-${row.key}`}
        state={state}
        onState={(change) => {
          const next = pickerReduce(state, change)
          const subject = data.subjects.find((s) => s.id === next.subjectId)
          const chapter = data.chapters.find((c) => c.id === next.chapterId)
          onChange({
            subjectId: next.subjectId,
            subjectKey: subject?.key ?? '',
            chapterId: next.chapterId,
            chapterLabel: subject && chapter ? `${subject.name} › ${chapter.name}` : '',
            topicId: next.chapterId === row.chapterId ? row.topicId : null,
            source: 'user',
          })
        }}
        subjects={data.subjects}
        chapters={data.chapters}
        topics={[]}
        loadingSubjects={data.loadingSubjects}
        loadingChapters={data.loadingChapters}
        withTopic={false}
      />
      {!subjectId && row.chapterId && row.chapterLabel ? (
        <p className="text-sm break-words text-muted-foreground">Now: {row.chapterLabel}</p>
      ) : null}
    </div>
  )
}

interface RangesStepContainerProps {
  rows: RangeRow[]
  onRows: (rows: RangeRow[]) => void
  pageCount: number | null
  /** The PDF's own contents list, once the file has been read (not before upload). */
  outline?: readonly OutlineNode[] | null
  /** Overlaps the server found (by row key); they clear when the student edits a row. */
  serverProblems?: RowProblems
  onClearServerProblems?: () => void
}

/** The Page ranges step: the rows with their validation, outline suggestions and a chapter picker per row. */
export function RangesStepContainer({
  rows,
  onRows,
  pageCount,
  outline,
  serverProblems = {},
  onClearServerProblems,
}: RangesStepContainerProps) {
  const levelId = useLevelId()
  const [suggesting, setSuggesting] = useState(false)
  const [note, setNote] = useState<string>()

  const problems = { ...validateRows(filledRows(rows), pageCount), ...serverProblems }
  const change = (key: string, patch: Partial<RangeRow>) => {
    onClearServerProblems?.()
    onRows(rows.map((r) => (r.key === key ? { ...r, ...patch } : r)))
  }

  const suggest = async () => {
    if (!pageCount || !outline || outline.length === 0) {
      setNote('This PDF has no contents list to start from. Add ranges by hand.')
      return
    }
    setSuggesting(true)
    setNote(undefined)
    const suggestions = rowsFromOutlineSuggestions(outline, pageCount).slice(0, SUGGEST_LIMIT)
    for (let i = 0; i < suggestions.length; i += SUGGEST_BATCH) {
      await Promise.all(
        suggestions.slice(i, i + SUGGEST_BATCH).map(async (row) => {
          const [best] = await suggestChapters(row.title, levelId).catch(() => [])
          if (best) {
            row.subjectId = best.subject_id
            row.subjectKey = best.subject_key
            row.chapterId = best.chapter_id
            row.chapterLabel = `${best.subject_name} › ${best.chapter_name}`
          }
        }),
      )
    }
    onRows(mergeSuggestions(rows, suggestions))
    setSuggesting(false)
    setNote('Suggested from the contents of the PDF. Check each chapter before saving.')
  }

  return (
    <PageRangeEditor
      rows={rows}
      problems={problems}
      pageCount={pageCount}
      onEdit={change}
      onAdd={() => onRows([...rows, emptyRow(nextRowStart(rows, pageCount))])}
      onRemove={(key) => {
        onClearServerProblems?.()
        onRows(rows.filter((r) => r.key !== key))
      }}
      renderChapter={(row) => <RangeRowChapter row={row} onChange={(patch) => change(row.key, patch)} />}
      onSuggest={outline ? () => void suggest() : undefined}
      suggesting={suggesting}
      note={note}
    />
  )
}
