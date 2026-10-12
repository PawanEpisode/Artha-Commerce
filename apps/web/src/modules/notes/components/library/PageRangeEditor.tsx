import { Button, ListTree, Plus, TextField, Trash2 } from '@artha/design-system'
import type { ReactNode } from 'react'

import type { RangeRow, RowProblems } from '../../lib/page-ranges'

interface PageRangeEditorProps {
  rows: readonly RangeRow[]
  problems: RowProblems
  pageCount: number | null
  onEdit: (key: string, change: Partial<Pick<RangeRow, 'from' | 'to'>>) => void
  onAdd: () => void
  onRemove: (key: string) => void
  /** The chapter fields of one row (a container: it reads the student's syllabus). */
  renderChapter: (row: RangeRow, index: number) => ReactNode
  /** Fills rows from the PDF's own outline (and guesses chapters with the server's text match). Not offered before upload. */
  onSuggest?: () => void
  suggesting?: boolean
  /** A line under the buttons ("Suggested from the contents. Check each chapter."). */
  note?: string
}

/**
 * Which pages of the PDF belong to which chapter (FR-F03-30): a row per range with first page, last page and chapter. A
 * mark takes its chapter from the range under it unless the student filed it somewhere else. Mistakes show on the row.
 * It only edits the rows; the dialog that holds it saves them with the rest of the details.
 */
export function PageRangeEditor({
  rows,
  problems,
  pageCount,
  onEdit,
  onAdd,
  onRemove,
  renderChapter,
  onSuggest,
  suggesting,
  note,
}: PageRangeEditorProps) {
  return (
    <section aria-label="Page ranges" className="space-y-3">
      <p className="text-sm text-muted-foreground">
        Say which pages belong to which chapter, so marks on those pages show up under that chapter.
        {pageCount ? ` This PDF has ${pageCount.toLocaleString('en-IN')} pages.` : ''} Optional.
      </p>

      {rows.length === 0 ? (
        <p className="rounded-xl border border-dashed border-border p-4 text-sm text-muted-foreground">
          No ranges yet. Add one{onSuggest ? ', or start from the contents of the PDF' : ''}.
        </p>
      ) : (
        <ul className="space-y-3">
          {rows.map((row, index) => {
            const problem = problems[row.key]
            const errorId = `range-${row.key}-error`
            return (
              <li key={row.key} data-slot="range-row">
                <fieldset className="space-y-3 rounded-xl border border-border bg-card p-3">
                  <legend className="px-1 text-xs font-semibold tracking-wide text-muted-foreground uppercase">
                    Range {index + 1}
                  </legend>
                  <div className="grid grid-cols-[1fr_1fr_auto] items-end gap-2">
                    <TextField
                      label="From page"
                      inputMode="numeric"
                      value={row.from}
                      aria-invalid={problem ? true : undefined}
                      aria-describedby={problem ? errorId : undefined}
                      onChange={(e) => onEdit(row.key, { from: e.target.value })}
                    />
                    <TextField
                      label="To page"
                      inputMode="numeric"
                      value={row.to}
                      aria-invalid={problem ? true : undefined}
                      aria-describedby={problem ? errorId : undefined}
                      onChange={(e) => onEdit(row.key, { to: e.target.value })}
                    />
                    <Button
                      variant="ghost"
                      size="icon"
                      aria-label={`Remove range ${index + 1}`}
                      onClick={() => onRemove(row.key)}
                    >
                      <Trash2 aria-hidden />
                    </Button>
                  </div>
                  {renderChapter(row, index)}
                  {problem ? (
                    <p id={errorId} role="alert" className="text-sm font-medium text-error-fg">
                      {problem}
                    </p>
                  ) : null}
                </fieldset>
              </li>
            )
          })}
        </ul>
      )}

      <div className="flex flex-wrap gap-2">
        <Button variant="outline" onClick={onAdd}>
          <Plus aria-hidden /> Add a range
        </Button>
        {onSuggest ? (
          <Button variant="outline" onClick={onSuggest} loading={suggesting}>
            <ListTree aria-hidden /> Start from the contents
          </Button>
        ) : null}
      </div>
      {note ? (
        <p role="status" className="text-sm text-muted-foreground">
          {note}
        </p>
      ) : null}
    </section>
  )
}
