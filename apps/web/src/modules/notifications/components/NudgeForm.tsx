import { SegmentedControl } from '@artha/design-system'
import { useEffect, useState } from 'react'

import { type Tone, TONES } from '../lib/schemas'
import { SwitchRow } from './SwitchRow'
import { TimeField } from './TimeField'

const TONE_LABEL: Record<Tone, string> = { calm: 'Calm', driven: 'Driven', celebratory: 'Celebratory' }

interface Props {
  enabled: boolean
  time: string
  tone: Tone
  onChange: (patch: { nudge_enabled?: boolean; nudge_time?: string; nudge_tone?: Tone }) => void
}

/** The daily nudge: on or off, around what time, and in what voice. */
export function NudgeForm({ enabled, time, tone, onChange }: Props) {
  const [draft, setDraft] = useState(time)
  useEffect(() => setDraft(time), [time])

  return (
    <div className="space-y-4">
      <SwitchRow
        id="nudge-enabled"
        label="Daily nudge"
        hint="A short message on days you have not opened Artha yet. It never comes during quiet hours."
        checked={enabled}
        onChange={(value) => onChange({ nudge_enabled: value })}
      />
      {enabled ? (
        <div className="grid gap-4 sm:grid-cols-2 sm:pl-15">
          <TimeField
            id="nudge-time"
            label="Around this time"
            value={draft}
            onValueChange={setDraft}
            onCommit={(value) => value !== time && onChange({ nudge_time: value })}
          />
          <div className="space-y-2">
            <p aria-hidden className="text-sm leading-none font-semibold">
              Tone
            </p>
            <SegmentedControl
              label="Tone of the daily nudge"
              value={tone}
              onValueChange={(value) => onChange({ nudge_tone: value })}
              options={TONES.map((value) => ({ value, label: TONE_LABEL[value] }))}
              className="w-full"
            />
          </div>
        </div>
      ) : null}
    </div>
  )
}
