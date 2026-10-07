import { Button, FolderInput, ListTree, Plus, TextField, Trash2 } from '@artha/design-system'

import type { RangeRow, RowProblems } from '../../lib/page-ranges'

interface PageRangeEditorProps {
  rows: readonly RangeRow[]
  problems: RowProblems
  pageCount: number | null
  onEdit: (key: string, change: Partial<Pick<RangeRow, 'from' | 'to'>>) => void
  onAdd: () => void
  onRemove: (key: string) => void
  /** Opens the chapter picker for one row. */
  onPickChapter: (key: string) => void
  /** Fills rows from the PDF's own outline (and guesses chapters with the server's text match). */
  onSuggest?: () => void
  suggesting?: boolean
  dirty: boolean
  saving: boolean
  onSave: () => void
  onReset: () => void
}

/**
 * Which pages of the PDF belong to which chapter (FR-F03-30): a row per range with first page, last page and chapter. A
 * mark takes its chapter from the range under it unless the student filed it somewhere else. Mistakes show on the row.
 */
export function PageRangeEditor({
  rows,
  problems,
  pageCount,
  onEdit,
  onAdd,
  onRemove,
  onPickChapter,
  onSuggest,
  suggesting,
  dirty,
  saving,
  onSave,
  onReset,
}: PageRangeEditorProps) {
  const hasProblems = Object.keys(problems).length > 0
  return (
    <section aria-labelledby="ranges-h" className="space-y-3">
      <div className="space-y-1">
        <h3 id="ranges-h" className="font-display text-lg font-bold">
          Page ranges
        </h3>
        <p className="text-sm text-muted-foreground">
          Say which pages belong to which chapter, so marks on those pages show up under that chapter.
          {pageCount ? ` This PDF has ${pageCount.toLocaleString('en-IN')} pages.` : ''}
        </p>
      </div>

      {rows.length === 0 ? (
        <p className="rounded-xl border border-dashed border-border p-4 text-sm text-muted-foreground">
          No ranges yet. Add one, or start from the contents of the PDF.
        </p>
      ) : (
        <ul className="space-y-3">
          {rows.map((row, index) => {
            const problem = problems[row.key]
            const errorId = `range-${row.key}-error`
            return (
              <li key={row.key} data-slot="range-row" className="space-y-2 rounded-xl border border-border bg-card p-3">
                <div className="grid grid-cols-[1fr_1fr_auto] items-end gap-2">
                  <TextField
                    label={`From page (range ${index + 1})`}
                    inputMode="numeric"
                    value={row.from}
                    aria-invalid={problem ? true : undefined}
                    aria-describedby={problem ? errorId : undefined}
                    onChange={(e) => onEdit(row.key, { from: e.target.value })}
                  />
                  <TextField
                    label={`To page (range ${index + 1})`}
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
                <Button
                  variant="outline"
                  className="max-w-full justify-start"
                  aria-label={`${row.chapterLabel || 'Choose a chapter'} for range ${index + 1}`}
                  onClick={() => onPickChapter(row.key)}
                >
                  <FolderInput aria-hidden />
                  <span className="min-w-0 truncate">{row.chapterLabel || 'Choose a chapter'}</span>
                </Button>
                {problem ? (
                  <p id={errorId} role="alert" className="text-sm font-medium text-error-fg">
                    {problem}
                  </p>
                ) : null}
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

      {dirty ? (
        <div className="flex flex-wrap gap-2">
          <Button onClick={onSave} disabled={hasProblems || saving} loading={saving}>
            Save page ranges
          </Button>
          <Button variant="ghost" onClick={onReset} disabled={saving}>
            Undo changes
          </Button>
        </div>
      ) : null}
    </section>
  )
}
