import { NumberStepper, PresetChips } from '@artha/design-system'

import { presetFor, TARGET_FIELDS, targetsLine, targetsOfPreset } from '../lib/targets'
import type { PresetKey, TargetPreset, Targets } from '../lib/types'

interface Props {
  value: Targets
  presets: ReadonlyArray<TargetPreset>
  limits: { min: number; max: number }
  onChange: (next: Targets) => void
  disabled?: boolean
}

/**
 * The presets and the three steppers, controlled. Shared by Settings and the onboarding step, so both read the same.
 * Picking a preset fills the numbers; changing a number by hand moves the highlight to none ("custom").
 */
export function TargetsFields({ value, presets, limits, onChange, disabled }: Props) {
  const active = presetFor(value, presets)
  const pick = (key: PresetKey) => {
    const preset = presets.find((p) => p.key === key)
    if (preset) onChange(targetsOfPreset(preset))
  }
  return (
    <div className="space-y-5">
      <PresetChips
        label="Study plan"
        value={active === 'custom' ? null : active}
        onValueChange={pick}
        disabled={disabled}
        options={presets.map((p) => ({ value: p.key, label: p.label, description: targetsLine(targetsOfPreset(p)) }))}
      />
      <ul className="space-y-4">
        {TARGET_FIELDS.map((f) => (
          <li key={f.key} className="flex items-center justify-between gap-4">
            <div>
              <p className="font-medium">{f.label}</p>
              <p className="text-sm text-muted-foreground">{value[f.key] === 0 ? 'Not tracked' : f.hint}</p>
            </div>
            <NumberStepper
              label={f.label}
              value={value[f.key]}
              min={limits.min}
              max={limits.max}
              disabled={disabled}
              onChange={(n) => onChange({ ...value, [f.key]: n })}
            />
          </li>
        ))}
      </ul>
      {active === 'custom' ? <p className="text-sm text-muted-foreground">Custom plan.</p> : null}
    </div>
  )
}
