import { Alert, Button, Card, Label, LoaderCircle, Select } from '@artha/design-system'
import { useState } from 'react'

import type { SwitchSummary } from '../lib/types'

interface Scheme {
  id: string
  code: string
  name: string
}

interface Props {
  current: Scheme
  options: Scheme[]
  pending: boolean
  error?: string
  summary?: SwitchSummary
  onSwitch: (to: Scheme) => void
}

/** Move to another published scheme. Mapped chapters keep their progress (FR-28). */
export function SchemeSwitch({ current, options, pending, error, summary, onSwitch }: Props) {
  const others = options.filter((s) => s.id !== current.id)
  const [target, setTarget] = useState('')
  const chosen = others.find((s) => s.id === target)
  return (
    <Card className="space-y-4 p-6">
      <div>
        <h2 className="font-display text-xl font-bold">Syllabus scheme</h2>
        <p className="mt-1 text-sm text-muted-foreground">You are on {current.name}.</p>
      </div>
      {summary ? (
        <Alert variant="success">
          Switched. {summary.carried_chapters} chapters carried your progress, {summary.new_chapters} are new
          {summary.removed_chapters
            ? `, and ${summary.removed_chapters} no longer exist in the new scheme (your old progress is kept)`
            : ''}
          .
        </Alert>
      ) : null}
      {others.length === 0 ? (
        <p className="text-sm text-muted-foreground">No other scheme is published for your level.</p>
      ) : (
        <div className="space-y-3">
          <div className="grid gap-2">
            <Label htmlFor="scheme-target">Switch to</Label>
            <Select id="scheme-target" value={target} onChange={(e) => setTarget(e.target.value)}>
              <option value="">Choose a scheme</option>
              {others.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}
                </option>
              ))}
            </Select>
          </div>
          {error ? <Alert variant="error">{error}</Alert> : null}
          <Button variant="outline" disabled={!chosen || pending} onClick={() => chosen && onSwitch(chosen)}>
            {pending ? <LoaderCircle className="animate-spin" aria-hidden /> : null}
            Switch scheme and carry over progress
          </Button>
        </div>
      )}
    </Card>
  )
}
