import * as React from 'react'

import { Eye, EyeOff } from '../../icons'
import { cn } from '../../lib/utils'
import { Input } from './input'
import { Label } from './label'

interface FieldProps extends Omit<React.ComponentProps<'input'>, 'id'> {
  id?: string
  label: string
  /** Helper text shown under the field. */
  hint?: string
  /** Validation message. Announced to screen readers and sets aria-invalid. */
  error?: string
}

function useFieldIds(idProp: string | undefined, hint?: string, error?: string) {
  const generated = React.useId()
  const id = idProp ?? generated
  const hintId = hint ? `${id}-hint` : undefined
  const errorId = error ? `${id}-error` : undefined
  const describedBy = [errorId, hintId].filter(Boolean).join(' ') || undefined
  return { id, hintId, errorId, describedBy }
}

function FieldMessages({
  hint,
  hintId,
  error,
  errorId,
}: {
  hint?: string
  hintId?: string
  error?: string
  errorId?: string
}) {
  return (
    <>
      {hint && (
        <p id={hintId} className="text-xs text-muted-foreground">
          {hint}
        </p>
      )}
      {error && (
        <p id={errorId} role="alert" className="text-xs font-medium text-destructive">
          {error}
        </p>
      )}
    </>
  )
}

/** Label + input + hint + error, wired for screen readers (label, aria-describedby, aria-invalid). */
export function TextField({ id: idProp, label, hint, error, className, ...props }: FieldProps) {
  const { id, hintId, errorId, describedBy } = useFieldIds(idProp, hint, error)
  return (
    <div className={cn('grid gap-1.5', className)}>
      <Label htmlFor={id}>{label}</Label>
      <Input id={id} aria-invalid={error ? true : undefined} aria-describedby={describedBy} {...props} />
      <FieldMessages hint={hint} hintId={hintId} error={error} errorId={errorId} />
    </div>
  )
}

/** Password input with a show/hide toggle (32px, 44px on touch). Never auto-fills the visible state. */
export function PasswordField({ id: idProp, label, hint, error, className, ...props }: Omit<FieldProps, 'type'>) {
  const { id, hintId, errorId, describedBy } = useFieldIds(idProp, hint, error)
  const [visible, setVisible] = React.useState(false)
  return (
    <div className={cn('grid gap-1.5', className)}>
      <Label htmlFor={id}>{label}</Label>
      <div className="relative">
        <Input
          id={id}
          type={visible ? 'text' : 'password'}
          aria-invalid={error ? true : undefined}
          aria-describedby={describedBy}
          className="pr-9"
          {...props}
        />
        <button
          type="button"
          onClick={() => setVisible((v) => !v)}
          aria-label={visible ? 'Hide password' : 'Show password'}
          aria-pressed={visible}
          className="absolute top-0 right-0 grid size-8 cursor-pointer place-items-center rounded-md text-muted-foreground outline-none hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring/50 pointer-coarse:size-11"
        >
          {visible ? <EyeOff className="size-4" aria-hidden /> : <Eye className="size-4" aria-hidden />}
        </button>
      </div>
      <FieldMessages hint={hint} hintId={hintId} error={error} errorId={errorId} />
    </div>
  )
}
