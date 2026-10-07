import {
  Button,
  Checkbox,
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
  FileDown,
  Switch,
  TextField,
} from '@artha/design-system'
import type { ReactNode } from 'react'

import type { DocumentSummary, MarkExportKind } from '../../lib/document-types'
import { EXPORT_KINDS, type ExportBlockReason, exportBlockText, type ExportForm } from '../../lib/export-options'
import type { ColorKey, ColorLegend } from '../../lib/library-types'
import { COLOR_KEYS } from '../../lib/library-types'
import type { Tag } from '../../lib/types'

interface ExportDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  doc: Pick<DocumentSummary, 'title' | 'page_count'>
  form: ExportForm
  onFormChange: (form: ExportForm) => void
  legend?: ColorLegend
  tags: readonly Tag[]
  /** Why the export cannot run (restricted, locked, not ready), or null. */
  blocked: ExportBlockReason | null
  online: boolean
  pagesError?: string
  /** A refusal from the server in plain words (limit reached, bad options). */
  error?: string
  busy: boolean
  /** The progress/result area, shown once a job exists. */
  status?: ReactNode
  onSubmit: () => void
}

const toggle = <T,>(list: readonly T[], value: T) =>
  list.includes(value) ? list.filter((x) => x !== value) : [...list, value]

/**
 * Export a flattened copy of the PDF with the student's marks burned in (FR-F03-53): page range, which kinds of marks,
 * colours by their legend names, tags, and an appendix of notes. Copy-restricted and locked files show the reason instead.
 */
export function ExportDialog({
  open,
  onOpenChange,
  doc,
  form,
  onFormChange,
  legend,
  tags,
  blocked,
  online,
  pagesError,
  error,
  busy,
  status,
  onSubmit,
}: ExportDialogProps) {
  const disabled = blocked !== null || !online
  const noKinds = form.include.length === 0
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogTitle className="flex items-center gap-2">
          <FileDown aria-hidden className="size-5" /> Export with my marks
        </DialogTitle>
        <DialogDescription className="break-words">
          {doc.title}. Your original stays as it is. You get a new PDF with your marks drawn on the pages.
        </DialogDescription>

        {blocked ? (
          <p role="alert" className="mt-4 rounded-xl border border-border bg-muted p-3 text-sm">
            {exportBlockText(blocked)}
          </p>
        ) : null}

        <form
          className="mt-4 space-y-5"
          onSubmit={(event) => {
            event.preventDefault()
            if (!disabled && !noKinds && !pagesError) onSubmit()
          }}
        >
          <fieldset disabled={disabled} className="space-y-5 disabled:opacity-60">
            <TextField
              label="Pages (optional)"
              hint={
                doc.page_count
                  ? `Leave empty for all ${doc.page_count.toLocaleString('en-IN')} pages. For example 1-40, 50.`
                  : 'Leave empty for all pages.'
              }
              value={form.pages}
              error={pagesError}
              inputMode="text"
              onChange={(e) => onFormChange({ ...form, pages: e.target.value })}
            />

            <div className="space-y-2">
              <p className="text-sm font-semibold">Include</p>
              <ul className="grid gap-1 sm:grid-cols-2">
                {EXPORT_KINDS.map((kind) => (
                  <li key={kind.value}>
                    <label className="flex min-h-11 cursor-pointer items-center gap-3 text-sm">
                      <Checkbox
                        checked={form.include.includes(kind.value)}
                        onCheckedChange={() =>
                          onFormChange({ ...form, include: toggle<MarkExportKind>(form.include, kind.value) })
                        }
                      />
                      {kind.label}
                    </label>
                  </li>
                ))}
              </ul>
              {noKinds ? (
                <p role="alert" className="text-sm font-medium text-error-fg">
                  Choose at least one kind of mark.
                </p>
              ) : null}
            </div>

            {legend ? (
              <div className="space-y-2">
                <p className="text-sm font-semibold">Colours (all if none chosen)</p>
                <ul className="grid gap-1 sm:grid-cols-2">
                  {COLOR_KEYS.map((key: ColorKey) => (
                    <li key={key}>
                      <label className="flex min-h-11 cursor-pointer items-center gap-3 text-sm">
                        <Checkbox
                          checked={form.colors.includes(key)}
                          onCheckedChange={() => onFormChange({ ...form, colors: toggle(form.colors, key) })}
                        />
                        <span className="min-w-0 break-words">{legend[key]}</span>
                      </label>
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}

            {tags.length > 0 ? (
              <div className="space-y-2">
                <p className="text-sm font-semibold">Only marks with these tags (all if none chosen)</p>
                <ul className="flex flex-wrap gap-2">
                  {tags.map((tag) => (
                    <li key={tag.id}>
                      <button
                        type="button"
                        aria-pressed={form.tags.includes(tag.id)}
                        onClick={() => onFormChange({ ...form, tags: toggle(form.tags, tag.id) })}
                        className="inline-flex min-h-11 items-center rounded-full border border-input bg-card px-4 text-sm font-medium outline-none hover:bg-muted focus-visible:ring-[3px] focus-visible:ring-ring/40 aria-pressed:border-primary aria-pressed:bg-secondary"
                      >
                        {tag.name}
                      </button>
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}

            <div className="flex min-h-11 items-center justify-between gap-3 text-sm font-semibold">
              <label htmlFor="export-appendix">
                Add my notes at the end
                <span className="block text-sm font-normal text-muted-foreground">
                  An appendix listing each mark with its comment.
                </span>
              </label>
              <Switch
                id="export-appendix"
                checked={form.appendix}
                onCheckedChange={(appendix) => onFormChange({ ...form, appendix })}
              />
            </div>
          </fieldset>

          {!online ? (
            <p className="text-sm text-muted-foreground">You are offline. Exports need a connection.</p>
          ) : null}
          {error ? (
            <p role="alert" className="text-sm font-medium text-error-fg">
              {error}
            </p>
          ) : null}

          {status}

          <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
            <Button type="button" variant="ghost" onClick={() => onOpenChange(false)}>
              Close
            </Button>
            <Button type="submit" variant="cta" disabled={disabled || noKinds || Boolean(pagesError)} loading={busy}>
              Build export
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  )
}
