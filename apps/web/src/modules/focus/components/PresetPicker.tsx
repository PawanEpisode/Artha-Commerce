import { DurationField, Label, NumberStepper, SegmentedControl } from '@artha/design-system'
import { useEffect, useState } from 'react'

import {
  describeTimings,
  FOCUS_MINUTES_MAX,
  LONG_BREAK_MINUTES_MAX,
  matchPreset,
  PRESET_LABELS,
  type PresetKey,
  presetTimings,
  ROUNDS_BEFORE_LONG_MAX,
  ROUNDS_BEFORE_LONG_MIN,
  SHORT_BREAK_MINUTES_MAX,
  timingErrors,
  type Timings,
} from '../lib/presets'

interface Props {
  value: Timings
  /** The saved choice. Custom can share a preset's lengths, so this is not inferred from the numbers alone. */
  preset?: PresetKey
  onChange: (timings: Timings, preset: PresetKey) => void
  disabled?: boolean
}

type DurationKey = 'focus_minutes' | 'short_break_minutes' | 'long_break_minutes'
type DurationDraft = Record<DurationKey, number | null>
const nullToZero = (d: DurationDraft) => ({
  focus_minutes: d.focus_minutes ?? 0,
  short_break_minutes: d.short_break_minutes ?? 0,
  long_break_minutes: d.long_break_minutes ?? 0,
})

const OPTIONS = (['classic', 'deep', 'light', 'custom'] as const).map((value) => ({
  value,
  label: PRESET_LABELS[value],
}))

/** Classic, Deep, Light or Custom. Custom shows four steppers bounded by the same limits the server enforces. */
export function PresetPicker({ value, preset, onChange, disabled }: Props) {
  const derived = preset ?? matchPreset(value)
  // Keep the click visible before a parent (or the server) echoes the new preset back.
  const [pending, setPending] = useState<PresetKey | null>(null)
  useEffect(() => {
    if (pending && derived === pending) setPending(null)
  }, [pending, derived])
  const selected = pending ?? derived
  // A duration being typed can be out of range for a moment. Keep it here, show why, and only report valid timings.
  const [draft, setDraft] = useState<DurationDraft>({
    focus_minutes: value.focus_minutes,
    short_break_minutes: value.short_break_minutes,
    long_break_minutes: value.long_break_minutes,
  })
  useEffect(() => {
    setDraft({
      focus_minutes: value.focus_minutes,
      short_break_minutes: value.short_break_minutes,
      long_break_minutes: value.long_break_minutes,
    })
  }, [value.focus_minutes, value.short_break_minutes, value.long_break_minutes])
  const errors = timingErrors({ ...value, ...nullToZero(draft) })
  const choose = (key: PresetKey) => {
    setPending(key)
    if (key === 'custom') onChange(value, 'custom')
    else onChange(presetTimings(key), key)
  }
  const setDuration = (key: DurationKey, minutes: number | null) => {
    setDraft((d) => ({ ...d, [key]: minutes }))
    if (!timingErrors({ ...value, [key]: minutes ?? 0 })[key]) set({ [key]: minutes ?? 0 })
  }
  const set = (patch: Partial<Timings>) => {
    const next = { ...value, ...patch }
    const key = matchPreset(next)
    setPending(key)
    onChange(next, key)
  }
  return (
    <div className="space-y-3">
      <div className="space-y-1.5">
        <Label>Preset</Label>
        <SegmentedControl
          label="Timer preset"
          value={selected}
          options={OPTIONS}
          disabled={disabled}
          stretch
          onValueChange={choose}
        />
        <p className="text-sm text-muted-foreground">{describeTimings(value)}</p>
        {selected === 'custom' ? (
          <p className="text-sm text-muted-foreground">
            Adjust the lengths below. They stay custom until you choose another preset.
          </p>
        ) : null}
      </div>
      {selected === 'custom' ? (
        <div className="grid gap-5 motion-safe:animate-in motion-safe:fade-in-0 motion-reduce:animate-none sm:grid-cols-2">
          <DurationField
            label="Focus length"
            size="compact"
            valueMinutes={draft.focus_minutes}
            onChangeMinutes={(n) => setDuration('focus_minutes', n)}
            maxMinutes={FOCUS_MINUTES_MAX}
            disabled={disabled}
            error={errors.focus_minutes}
          />
          <DurationField
            label="Short break"
            size="compact"
            valueMinutes={draft.short_break_minutes}
            onChangeMinutes={(n) => setDuration('short_break_minutes', n)}
            maxMinutes={SHORT_BREAK_MINUTES_MAX}
            disabled={disabled}
            error={errors.short_break_minutes}
          />
          <DurationField
            label="Long break"
            size="compact"
            valueMinutes={draft.long_break_minutes}
            onChangeMinutes={(n) => setDuration('long_break_minutes', n)}
            maxMinutes={LONG_BREAK_MINUTES_MAX}
            disabled={disabled}
            error={errors.long_break_minutes}
          />
          <Field label="Rounds before a long break">
            <NumberStepper
              label="Rounds before a long break"
              value={value.rounds_before_long}
              min={ROUNDS_BEFORE_LONG_MIN}
              max={ROUNDS_BEFORE_LONG_MAX}
              disabled={disabled}
              onChange={(n) => set({ rounds_before_long: n })}
            />
          </Field>
        </div>
      ) : null}
    </div>
  )
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="space-y-1.5">
      <p className="text-sm font-medium">{label}</p>
      {children}
    </div>
  )
}
