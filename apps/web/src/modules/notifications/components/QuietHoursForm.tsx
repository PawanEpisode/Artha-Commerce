import { useEffect, useState } from 'react'

import { describeQuietHours, quietHoursError } from '../lib/quietHours'
import { SwitchRow } from './SwitchRow'
import { TimeField } from './TimeField'

interface Props {
  enabled: boolean
  start: string
  end: string
  onChange: (patch: { quiet_enabled?: boolean; quiet_start?: string; quiet_end?: string }) => void
}

/** Quiet hours: a switch and two times. A time saves only when the pair is valid; otherwise the field says why. */
export function QuietHoursForm({ enabled, start, end, onChange }: Props) {
  const [draftStart, setDraftStart] = useState(start)
  const [draftEnd, setDraftEnd] = useState(end)
  useEffect(() => setDraftStart(start), [start])
  useEffect(() => setDraftEnd(end), [end])

  const error = enabled ? quietHoursError(draftStart, draftEnd) : null

  const commit = (field: 'quiet_start' | 'quiet_end', value: string) => {
    const nextStart = field === 'quiet_start' ? value : draftStart
    const nextEnd = field === 'quiet_end' ? value : draftEnd
    if (quietHoursError(nextStart, nextEnd)) return
    if (value !== (field === 'quiet_start' ? start : end)) onChange({ [field]: value })
  }

  return (
    <div className="space-y-4">
      <SwitchRow
        id="quiet-enabled"
        label="Quiet hours"
        hint="Reminders wait until the quiet time ends. Alerts for a timer you started yourself still come through."
        checked={enabled}
        onChange={(value) => onChange({ quiet_enabled: value })}
      />
      {enabled ? (
        <div className="space-y-2 pl-0 sm:pl-15">
          <div className="grid gap-4 sm:grid-cols-2">
            <TimeField
              id="quiet-start"
              label="Quiet from"
              value={draftStart}
              onValueChange={setDraftStart}
              onCommit={(value) => commit('quiet_start', value)}
              error={error ?? undefined}
            />
            <TimeField
              id="quiet-end"
              label="Quiet until"
              value={draftEnd}
              onValueChange={setDraftEnd}
              onCommit={(value) => commit('quiet_end', value)}
            />
          </div>
          {error ? null : <p className="text-sm text-muted-foreground">{describeQuietHours(draftStart, draftEnd)}</p>}
        </div>
      ) : null}
    </div>
  )
}
