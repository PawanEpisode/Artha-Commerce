import { Alert, Button, CalendarClock, TextField } from '@artha/design-system'
import { useState } from 'react'

import { examDateError, type TermOption } from '../lib/exam'
import { formatDay } from '../lib/time'

export interface ExamDateCardProps {
  terms: readonly TermOption[]
  today: string
  pending: boolean
  error?: string | null
  onPickTerm: (term: TermOption) => void
  onCustomDate: (date: string) => void
  onDismiss: () => void
}

/** "Pick your attempt so we can pace you": the F-02 terms as chips, or the student's own date. Dismissible; setting one rebuilds the plan once. */
export function ExamDateCard({ terms, today, pending, error, onPickTerm, onCustomDate, onDismiss }: ExamDateCardProps) {
  const [custom, setCustom] = useState(false)
  const [date, setDate] = useState('')
  const [fieldError, setFieldError] = useState<string | null>(null)

  const save = () => {
    const found = examDateError(date, today)
    setFieldError(found)
    if (!found) onCustomDate(date)
  }

  return (
    <section
      aria-labelledby="exam-card-heading"
      className="space-y-4 rounded-2xl border border-border bg-card p-4 sm:p-5"
    >
      <div className="flex items-start gap-3">
        <CalendarClock aria-hidden className="mt-1 size-5 shrink-0 text-primary" />
        <div className="min-w-0 space-y-1">
          <h2 id="exam-card-heading" className="font-display text-lg font-bold">
            Pick your attempt so we can pace you
          </h2>
          <p className="text-sm text-muted-foreground">
            With your exam date we plan more revision as it gets closer. You can change it later in your coverage
            settings.
          </p>
        </div>
      </div>
      {error ? <Alert variant="error">{error}</Alert> : null}
      {terms.length > 0 ? (
        <div role="group" aria-label="Exam attempts" className="flex flex-wrap gap-2">
          {terms.map((term) => (
            <Button key={term.id} variant="outline" disabled={pending} onClick={() => onPickTerm(term)}>
              {term.name}
              {term.exam_start ? ` · ${formatDay(term.exam_start)}` : ''}
            </Button>
          ))}
        </div>
      ) : null}
      {custom ? (
        <form
          className="flex flex-wrap items-end gap-3"
          onSubmit={(e) => {
            e.preventDefault()
            save()
          }}
          noValidate
        >
          <TextField
            label="Exam date"
            type="date"
            min={today}
            value={date}
            onChange={(e) => setDate(e.target.value)}
            error={fieldError ?? undefined}
          />
          <Button type="submit" disabled={pending}>
            {pending ? 'Saving' : 'Save date'}
          </Button>
        </form>
      ) : (
        <Button variant="ghost" size="sm" onClick={() => setCustom(true)}>
          Set my own date
        </Button>
      )}
      <div>
        <Button variant="ghost" size="sm" onClick={onDismiss}>
          Not now
        </Button>
      </div>
    </section>
  )
}
