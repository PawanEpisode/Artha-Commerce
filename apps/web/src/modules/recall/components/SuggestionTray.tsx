import {
  Alert,
  Badge,
  Button,
  Check,
  DataTable,
  Label,
  Pencil,
  Quote,
  Skeleton,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
  Textarea,
  X,
} from '@artha/design-system'
import { useId, useState } from 'react'

import type { Suggestion, SuggestionBatch } from '../lib/schemas'
import { batchSummary, decidedText, fieldLabel, isActive, isLongField, pendingDrafts } from '../lib/suggestions'
import { kindLabel } from './CardFace'
import { InlineText } from './InlineText'

interface TrayProps {
  batch: SuggestionBatch
  busyId: string | null
  /** A sentence for the last accept or reject that failed (the suggestion it was about is kept on screen). */
  error: { id: string; text: string } | null
  onAccept: (s: Suggestion, fields?: Record<string, string>) => void
  onReject: (s: Suggestion) => void
}

/**
 * One suggestion as a table row: the card (kind, status, front and back, or the edit fields), the quote that backs it and the
 * three decisions. Under 768px the row stacks, so nothing scrolls sideways.
 */
function SuggestionRow({
  s,
  busy,
  error,
  onAccept,
  onReject,
}: {
  s: Suggestion
  busy: boolean
  error: string | null
  onAccept: TrayProps['onAccept']
  onReject: TrayProps['onReject']
}) {
  const id = useId()
  const [editing, setEditing] = useState(false)
  const [fields, setFields] = useState<Record<string, string>>(s.fields)
  const decided = decidedText(s)
  const open = s.status === 'draft'
  const keys = Object.keys(s.fields)
  const edited = keys.some((k) => fields[k] !== s.fields[k])

  return (
    <TableRow className="align-top max-md:flex max-md:flex-col">
      <TableCell className="h-auto min-w-0 space-y-2 py-3 align-top md:w-[42%]">
        <div className="flex flex-wrap items-center gap-1.5">
          <Badge variant="outline">{kindLabel(s.kind)}</Badge>
          {decided ? (
            <Badge variant={s.status === 'rejected' || s.status === 'expired' ? 'default' : 'accent'}>{decided}</Badge>
          ) : null}
        </div>
        {editing ? (
          <div className="space-y-2">
            {keys.map((k) => (
              <div key={k} className="space-y-1">
                <Label htmlFor={`${id}-${k}`}>{fieldLabel(k)}</Label>
                <Textarea
                  id={`${id}-${k}`}
                  value={fields[k] ?? ''}
                  rows={isLongField(k) ? 4 : 2}
                  onChange={(e) => setFields({ ...fields, [k]: e.target.value })}
                />
              </div>
            ))}
          </div>
        ) : (
          <div className="space-y-2">
            <div>
              <p className="text-[11px] font-medium tracking-wide text-muted-foreground uppercase">Front</p>
              <div className="leading-snug">
                <InlineText text={s.front_md} />
              </div>
            </div>
            <div>
              <p className="text-[11px] font-medium tracking-wide text-muted-foreground uppercase">Back</p>
              <div className="leading-snug">
                <InlineText text={s.back_md} />
              </div>
            </div>
          </div>
        )}
        {error ? <Alert variant="error">{error}</Alert> : null}
      </TableCell>
      <TableCell className="h-auto min-w-0 py-3 align-top">
        <figure className="space-y-1 text-[13px]">
          <figcaption className="flex items-center gap-1.5 font-medium text-muted-foreground">
            <Quote aria-hidden className="size-3.5" /> From {s.evidence_label}
          </figcaption>
          <blockquote className="text-foreground">{s.evidence_quote}</blockquote>
        </figure>
      </TableCell>
      <TableCell className="h-auto py-3 align-top md:w-0">
        {open ? (
          <div className="flex flex-wrap gap-1.5 md:flex-col md:items-stretch">
            <Button size="sm" disabled={busy} onClick={() => onAccept(s, editing && edited ? fields : undefined)}>
              <Check aria-hidden /> {editing && edited ? 'Save my version as a card' : 'Add as a card'}
            </Button>
            <Button
              size="sm"
              variant="outline"
              disabled={busy}
              aria-pressed={editing}
              onClick={() => {
                setEditing(!editing)
                setFields(s.fields)
              }}
            >
              <Pencil aria-hidden /> {editing ? 'Stop editing' : 'Edit first'}
            </Button>
            <Button size="sm" variant="ghost" disabled={busy} onClick={() => onReject(s)}>
              <X aria-hidden /> Not useful
            </Button>
          </div>
        ) : null}
      </TableCell>
    </TableRow>
  )
}

/** One batch: a line about how it went, then a table of suggestions, each with the quote that backs it. */
export function SuggestionTray({ batch, busyId, error, onAccept, onReject }: TrayProps) {
  if (isActive(batch)) {
    return (
      <div role="status" aria-live="polite" className="space-y-2">
        <p className="font-medium">{batchSummary(batch)}</p>
        {batch.estimate_seconds ? (
          <p className="text-[13px] text-muted-foreground">
            This usually takes about {batch.estimate_seconds} seconds.
          </p>
        ) : null}
        <Skeleton className="h-9 w-full" />
        <Skeleton className="h-9 w-full" />
        <Skeleton className="h-9 w-full" />
      </div>
    )
  }
  const failed = batch.status === 'failed' || batch.status === 'cancelled'
  const waiting = pendingDrafts(batch).length
  return (
    <section className="space-y-2" aria-label="Suggested cards">
      <p role="status" className="font-medium">
        {batchSummary(batch)}
      </p>
      {failed ? null : batch.suggestions.length === 0 ? (
        <p className="text-muted-foreground">There is nothing to review.</p>
      ) : (
        <>
          {waiting > 0 ? (
            <p className="text-[13px] text-muted-foreground">
              {waiting} left to decide. Each card has the exact words from your material that back it.
            </p>
          ) : (
            <p className="text-[13px] text-muted-foreground">You have decided all of them.</p>
          )}
          <DataTable aria-label="Suggestions">
            <TableHeader className="max-md:sr-only">
              <TableRow>
                <TableHead>Card</TableHead>
                <TableHead>Source</TableHead>
                <TableHead>
                  <span className="sr-only">Decision</span>
                </TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {batch.suggestions.map((s) => (
                <SuggestionRow
                  key={s.id}
                  s={s}
                  busy={busyId === s.id}
                  error={error?.id === s.id ? error.text : null}
                  onAccept={onAccept}
                  onReject={onReject}
                />
              ))}
            </TableBody>
          </DataTable>
        </>
      )}
    </section>
  )
}
