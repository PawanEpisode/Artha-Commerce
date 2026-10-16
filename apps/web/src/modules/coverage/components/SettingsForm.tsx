import { Alert, Button, Card, Label, LoaderCircle, NumberStepper, Switch, TextField } from '@artha/design-system'
import { type FormEvent, useState } from 'react'

import { DEFAULT_REVISION_DAYS, DEFAULT_WEIGHTS, revisionDaysValid, weightsTotal, weightsValid } from '../lib/formula'
import type { WeightSettings } from '../lib/types'

interface Props {
  settings: WeightSettings
  pending: boolean
  error?: string
  saved?: boolean
  onSave: (next: WeightSettings) => void
  onReset: () => void
}

const parseDays = (text: string): number[] =>
  text
    .split(/[,\s]+/)
    .filter(Boolean)
    .map(Number)

/** Weights (must total 100), revision schedule and the default roll-up view (FR-25). */
export function SettingsForm({ settings, pending, error, saved, onSave, onReset }: Props) {
  const [w, setW] = useState({
    read: settings.w_read,
    practice: settings.w_practice,
    revise: settings.w_revise,
    mock: settings.w_mock,
  })
  const [days, setDays] = useState(settings.revision_days.join(', '))
  const [weighted, setWeighted] = useState(settings.weighted_default)

  const total = weightsTotal(w)
  const parsedDays = parseDays(days)
  const daysOk = revisionDaysValid(parsedDays)
  const canSave = weightsValid(w) && daysOk && !pending

  function submit(e: FormEvent) {
    e.preventDefault()
    if (!canSave) return
    onSave({
      w_read: w.read,
      w_practice: w.practice,
      w_revise: w.revise,
      w_mock: w.mock,
      revision_days: parsedDays,
      weighted_default: weighted,
    })
  }

  function resetLocal() {
    setW(DEFAULT_WEIGHTS)
    setDays(DEFAULT_REVISION_DAYS.join(', '))
    setWeighted(false)
    onReset()
  }

  const row = (key: keyof typeof w, label: string) => (
    <div className="flex items-center justify-between gap-4 px-4 py-2.5">
      <span className="text-[13px] font-medium">{label}</span>
      <NumberStepper
        label={`${label} weight`}
        value={w[key]}
        min={0}
        max={100}
        step={5}
        onChange={(v) => setW((p) => ({ ...p, [key]: v }))}
      />
    </div>
  )

  return (
    <form onSubmit={submit} noValidate className="space-y-4">
      <Card className="divide-y">
        <div className="p-4">
          <h2 className="text-sm font-semibold">How coverage is weighed</h2>
          <p className="text-xs text-muted-foreground">
            Decide how much each part counts towards a chapter&apos;s percent.
          </p>
        </div>
        {row('read', 'Reading')}
        {row('practice', 'Practice')}
        {row('revise', 'Revision')}
        {row('mock', 'Mock tests')}
        <p
          role="status"
          className={`px-4 py-2.5 text-[13px] font-semibold ${total === 100 ? 'text-muted-foreground' : 'text-destructive'}`}
        >
          Total: {total}%{' '}
          {total === 100 ? '' : `(must be 100, ${total > 100 ? `${total - 100} over` : `${100 - total} short`})`}
        </p>
        <div className="space-y-3 p-4">
          <div>
            <h2 className="text-sm font-semibold">Revision schedule</h2>
            <p className="text-xs text-muted-foreground">
              Days after each revision until the next one is due. The last gap repeats.
            </p>
          </div>
          <TextField
            label="Days between revisions"
            value={days}
            onChange={(e) => setDays(e.target.value)}
            inputMode="numeric"
            hint="For example: 3, 7, 21, 45"
            error={daysOk ? undefined : 'Enter 1 to 8 whole numbers between 1 and 365, separated by commas.'}
          />
        </div>
        <div className="flex items-center justify-between gap-4 p-4">
          <div className="min-w-0">
            <Label htmlFor="weighted-default" className="text-[13px] font-semibold">
              Weight by marks by default
            </Label>
            <p className="mt-0.5 text-xs text-muted-foreground">
              Chapters with more marks count more in subject and level percentages.
            </p>
          </div>
          <Switch id="weighted-default" checked={weighted} onCheckedChange={setWeighted} />
        </div>
      </Card>

      {error ? <Alert variant="error">{error}</Alert> : null}
      {saved && !error ? <Alert variant="success">Saved. Your percentages are updated.</Alert> : null}
      <div className="flex flex-wrap gap-2">
        <Button type="submit" disabled={!canSave}>
          {pending ? <LoaderCircle className="animate-spin" aria-hidden /> : null}
          Save settings
        </Button>
        <Button type="button" variant="outline" onClick={resetLocal} disabled={pending}>
          Reset to defaults
        </Button>
      </div>
    </form>
  )
}
