import { Alert, Badge, Button, Card, Check, Label, Pencil, Quote, Skeleton, Textarea, X } from '@artha/design-system'
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

function SuggestionCard({
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
    <li className="list-none">
      <Card className="space-y-4 p-4 sm:p-5">
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant="outline">{kindLabel(s.kind)}</Badge>
          {decided ? (
            <Badge variant={s.status === 'rejected' || s.status === 'expired' ? 'default' : 'accent'}>{decided}</Badge>
          ) : null}
        </div>

        {editing ? (
          <div className="space-y-3">
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
          <div className="space-y-3">
            <div>
              <p className="text-xs font-semibold tracking-wide text-muted-foreground uppercase">Front</p>
              <div className="text-base leading-relaxed">
                <InlineText text={s.front_md} />
              </div>
            </div>
            <div>
              <p className="text-xs font-semibold tracking-wide text-muted-foreground uppercase">Back</p>
              <div className="text-base leading-relaxed">
                <InlineText text={s.back_md} />
              </div>
            </div>
          </div>
        )}

        <figure className="mt-3 rounded-lg border border-border bg-muted p-3 text-sm">
          <figcaption className="mb-1 flex items-center gap-1.5 font-medium text-muted-foreground">
            <Quote aria-hidden className="size-4" /> From {s.evidence_label}
          </figcaption>
          <blockquote className="text-foreground">{s.evidence_quote}</blockquote>
        </figure>

        {error ? (
          <Alert variant="error" className="mt-3">
            {error}
          </Alert>
        ) : null}

        {open ? (
          <div className="mt-3 flex flex-wrap gap-2">
            <Button disabled={busy} onClick={() => onAccept(s, editing && edited ? fields : undefined)}>
              <Check aria-hidden /> {editing && edited ? 'Save my version as a card' : 'Add as a card'}
            </Button>
            <Button
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
            <Button variant="ghost" disabled={busy} onClick={() => onReject(s)}>
              <X aria-hidden /> Not useful
            </Button>
          </div>
        ) : null}
      </Card>
    </li>
  )
}

/** One batch: a line about how it went, then each suggestion with the quote that backs it. */
export function SuggestionTray({ batch, busyId, error, onAccept, onReject }: TrayProps) {
  if (isActive(batch)) {
    return (
      <div role="status" aria-live="polite" className="space-y-3">
        <p className="font-medium">{batchSummary(batch)}</p>
        {batch.estimate_seconds ? (
          <p className="text-sm text-muted-foreground">This usually takes about {batch.estimate_seconds} seconds.</p>
        ) : null}
        <Skeleton className="h-28 w-full" />
        <Skeleton className="h-28 w-full" />
      </div>
    )
  }
  const failed = batch.status === 'failed' || batch.status === 'cancelled'
  const waiting = pendingDrafts(batch).length
  return (
    <section className="space-y-3" aria-label="Suggested cards">
      <p role="status" className="font-medium">
        {batchSummary(batch)}
      </p>
      {failed ? null : batch.suggestions.length === 0 ? (
        <p className="text-muted-foreground">There is nothing to review.</p>
      ) : (
        <>
          {waiting > 0 ? (
            <p className="text-sm text-muted-foreground">
              {waiting} left to decide. Each card has the exact words from your material that back it.
            </p>
          ) : (
            <p className="text-sm text-muted-foreground">You have decided all of them.</p>
          )}
          <ul className="space-y-3">
            {batch.suggestions.map((s) => (
              <SuggestionCard
                key={s.id}
                s={s}
                busy={busyId === s.id}
                error={error?.id === s.id ? error.text : null}
                onAccept={onAccept}
                onReject={onReject}
              />
            ))}
          </ul>
        </>
      )}
    </section>
  )
}
