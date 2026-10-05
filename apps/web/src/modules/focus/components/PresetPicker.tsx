import { Alert, Label, NumberStepper, SegmentedControl } from '@artha/design-system'
import { useEffect, useState } from 'react'

import {
  describeTimings,
  FOCUS_MINUTES_MAX,
  FOCUS_MINUTES_MIN,
  LONG_BREAK_MINUTES_MAX,
  LONG_BREAK_MINUTES_MIN,
  matchPreset,
  PRESET_LABELS,
  type PresetKey,
  presetTimings,
  ROUNDS_BEFORE_LONG_MAX,
  ROUNDS_BEFORE_LONG_MIN,
  SHORT_BREAK_MINUTES_MAX,
  SHORT_BREAK_MINUTES_MIN,
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
  const errors = timingErrors(value)
  const choose = (key: PresetKey) => {
    setPending(key)
    if (key === 'custom') onChange(value, 'custom')
    else onChange(presetTimings(key), key)
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
        <div className="grid gap-4 motion-safe:animate-in motion-safe:fade-in-0 motion-reduce:animate-none sm:grid-cols-2">
          <Field label="Focus (minutes)">
            <NumberStepper
              label="Focus minutes"
              value={value.focus_minutes}
              min={FOCUS_MINUTES_MIN}
              max={FOCUS_MINUTES_MAX}
              step={5}
              disabled={disabled}
              onChange={(n) => set({ focus_minutes: n })}
            />
          </Field>
          <Field label="Short break (minutes)">
            <NumberStepper
              label="Short break minutes"
              value={value.short_break_minutes}
              min={SHORT_BREAK_MINUTES_MIN}
              max={SHORT_BREAK_MINUTES_MAX}
              disabled={disabled}
              onChange={(n) => set({ short_break_minutes: n })}
            />
          </Field>
          <Field label="Long break (minutes)">
            <NumberStepper
              label="Long break minutes"
              value={value.long_break_minutes}
              min={LONG_BREAK_MINUTES_MIN}
              max={LONG_BREAK_MINUTES_MAX}
              step={5}
              disabled={disabled}
              onChange={(n) => set({ long_break_minutes: n })}
            />
          </Field>
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
      {Object.values(errors).length > 0 ? (
        <Alert variant="error">
          <span role="alert">{Object.values(errors)[0]}</span>
        </Alert>
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
