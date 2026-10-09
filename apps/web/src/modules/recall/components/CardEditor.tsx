import { cn, Input, Label, SegmentedControl, Textarea } from '@artha/design-system'
import { useId } from 'react'

import { RichText } from '~/lib/richtext'

import { type CardKind, facesOf, type FieldIssue, type Fields, formFields, renderFace } from '../lib/cardKinds'

export type Importance = 'bullet' | 'important' | 'mandatory'
const IMPORTANCE = [
  { value: 'bullet', label: 'Normal' },
  { value: 'important', label: 'Important' },
  { value: 'mandatory', label: 'Must know' },
] as const

function Counter({ id, length, max }: { id: string; length: number; max: number }) {
  const near = length > max * 0.9
  return (
    <p
      id={id}
      className={cn(
        'text-xs tabular-nums',
        length > max ? 'font-medium text-destructive' : near ? 'text-foreground' : 'text-muted-foreground',
      )}
    >
      {length} of {max} characters
    </p>
  )
}

function FieldBox({
  name,
  label,
  hint,
  required,
  short,
  max,
  value,
  error,
  disabled,
  onChange,
}: {
  name: string
  label: string
  hint?: string
  required: boolean
  short: boolean
  max: number
  value: string
  error?: string
  disabled?: boolean
  onChange: (value: string) => void
}) {
  const uid = useId()
  const id = `${uid}-${name}`
  const describedBy = [error ? `${id}-error` : null, hint ? `${id}-hint` : null, `${id}-count`]
    .filter(Boolean)
    .join(' ')
  const common = {
    id,
    value,
    disabled,
    'aria-invalid': error ? true : undefined,
    'aria-describedby': describedBy,
    'aria-required': required || undefined,
  }
  return (
    <div className="grid gap-2">
      <Label htmlFor={id}>
        {label}
        {required ? null : <span className="font-normal text-muted-foreground"> (optional)</span>}
      </Label>
      {short ? (
        <Input {...common} onChange={(e) => onChange(e.target.value)} />
      ) : (
        <Textarea {...common} rows={3} className="min-h-24" onChange={(e) => onChange(e.target.value)} />
      )}
      {hint ? (
        <p id={`${id}-hint`} className="text-sm text-muted-foreground">
          {hint}
        </p>
      ) : null}
      {error ? (
        <p id={`${id}-error`} role="alert" className="text-sm font-medium text-destructive">
          {error}
        </p>
      ) : null}
      <Counter id={`${id}-count`} length={[...value].length} max={max} />
    </div>
  )
}

/** The fields of one kind, with counters and errors, and the importance and tags every card has. */
export function CardFields({
  kind,
  fields,
  onField,
  issues,
  disabled,
}: {
  kind: CardKind
  fields: Fields
  onField: (name: string, value: string) => void
  issues: readonly FieldIssue[]
  disabled?: boolean
}) {
  return (
    <>
      {formFields(kind).map((f) => (
        <FieldBox
          key={f.name}
          {...f}
          value={fields[f.name] ?? ''}
          error={issues.find((i) => i.field === f.name)?.message}
          disabled={disabled}
          onChange={(v) => onField(f.name, v)}
        />
      ))}
    </>
  )
}

export function ImportanceField({
  value,
  onChange,
  disabled,
}: {
  value: Importance
  onChange: (v: Importance) => void
  disabled?: boolean
}) {
  return (
    <div className="grid gap-2">
      <span className="text-sm font-medium">How important is it?</span>
      <SegmentedControl
        label="How important is it?"
        value={value}
        onValueChange={onChange}
        options={IMPORTANCE}
        stretch
        aria-disabled={disabled}
      />
    </div>
  )
}

export function TagsField({
  value,
  onChange,
  error,
  disabled,
}: {
  value: string
  onChange: (v: string) => void
  error?: string | null
  disabled?: boolean
}) {
  const id = useId()
  return (
    <div className="grid gap-2">
      <Label htmlFor={id}>
        Tags <span className="font-normal text-muted-foreground">(optional)</span>
      </Label>
      <Input
        id={id}
        value={value}
        disabled={disabled}
        onChange={(e) => onChange(e.target.value)}
        aria-invalid={error ? true : undefined}
        aria-describedby={`${id}-hint`}
      />
      <p
        id={`${id}-hint`}
        className={cn('text-sm', error ? 'font-medium text-destructive' : 'text-muted-foreground')}
        role={error ? 'alert' : undefined}
      >
        {error ?? 'Separate tags with commas.'}
      </p>
    </div>
  )
}

/** What the card will look like in review, as the text is typed. One block per hidden word for fill in the blank. */
export function CardPreview({ kind, fields }: { kind: CardKind; fields: Fields }) {
  const faces = facesOf(kind, fields)
  return (
    <section aria-label="Preview" className="space-y-3 rounded-2xl border border-border bg-muted/40 p-4">
      <h2 className="text-sm font-semibold text-muted-foreground">Preview</h2>
      {faces.length === 0 ? <p className="text-sm text-muted-foreground">Add a hidden word to see the cards.</p> : null}
      {faces.map((ordinal) => {
        const [front, back] = renderFace(kind, fields, ordinal)
        return (
          <div key={ordinal} className="grid gap-3 sm:grid-cols-2">
            <div className="space-y-1">
              <p className="text-xs font-medium tracking-wide text-muted-foreground uppercase">Front</p>
              <RichText markdown={front || ' '} profile="card" />
            </div>
            <div className="space-y-1">
              <p className="text-xs font-medium tracking-wide text-muted-foreground uppercase">Back</p>
              <RichText markdown={back || ' '} profile="card" />
            </div>
          </div>
        )
      })}
    </section>
  )
}
