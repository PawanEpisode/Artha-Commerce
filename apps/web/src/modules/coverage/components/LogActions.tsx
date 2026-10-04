import { Button, Label, LoaderCircle, Select, TextField } from '@artha/design-system'
import { type FormEvent, useState } from 'react'

import type { EventType } from '../lib/types'

interface Props {
  pending?: boolean
  error?: string
  onLog: (type: EventType, value: number | null) => void
}

const OPTIONS: Array<{ value: EventType; label: string; scored: boolean }> = [
  { value: 'practice_done', label: 'Practice set', scored: true },
  { value: 'mock_done', label: 'Mock test or past paper', scored: true },
  { value: 'revision_done', label: 'Revision', scored: false },
]

/** Log a practice set, mock or revision (FR-15). Score is optional and a percent. */
export function LogActions({ pending, error, onLog }: Props) {
  const [type, setType] = useState<EventType>('practice_done')
  const [score, setScore] = useState('')
  const scored = OPTIONS.find((o) => o.value === type)?.scored ?? false
  const parsed = score.trim() === '' ? null : Number(score)
  const invalid = scored && parsed !== null && (!Number.isFinite(parsed) || parsed < 0 || parsed > 100)

  function submit(e: FormEvent) {
    e.preventDefault()
    if (invalid) return
    onLog(type, scored ? parsed : null)
    setScore('')
  }

  return (
    <form onSubmit={submit} noValidate className="grid gap-4 sm:grid-cols-[1fr_9rem_auto] sm:items-end">
      <div className="grid gap-2">
        <Label htmlFor="log-type">What did you finish?</Label>
        <Select id="log-type" value={type} onChange={(e) => setType(e.target.value as EventType)}>
          {OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </Select>
      </div>
      {scored ? (
        <TextField
          label="Score (optional)"
          inputMode="decimal"
          placeholder="0 to 100"
          value={score}
          onChange={(e) => setScore(e.target.value)}
          error={invalid ? 'Enter a score from 0 to 100.' : undefined}
        />
      ) : (
        <span aria-hidden className="hidden sm:block" />
      )}
      <Button type="submit" disabled={pending || invalid}>
        {pending ? <LoaderCircle className="animate-spin" aria-hidden /> : null}
        Log it
      </Button>
      {error ? (
        <p role="alert" className="text-sm font-medium text-destructive sm:col-span-3">
          {error}
        </p>
      ) : null}
    </form>
  )
}
