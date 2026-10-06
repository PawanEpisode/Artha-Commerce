import { Alert, Button, Label, Slider, Switch } from '@artha/design-system'

import type { PresetKey, Timings } from '../lib/presets'
import type { FocusSettings } from '../lib/types'
import { PresetPicker } from './PresetPicker'

interface Props {
  value: FocusSettings
  onChange: (patch: Partial<FocusSettings>) => void
  onTimingsChange: (timings: Timings, preset: PresetKey) => void
  onPreview: () => void
  /** Whether this browser can hold the screen awake; the switches still save, the note says what will happen. */
  wakeLockSupported?: boolean
  /** The `keep_awake` flag: false hides the screen section. */
  showKeepAwake?: boolean
  /** The browser's notification permission, so the switch can explain a block. */
  permission: 'granted' | 'denied' | 'default' | 'unsupported'
  busy: boolean
  /** Optional inline message for a problem the form itself can explain. API failures are toasts. */
  error?: string | null
}

/** Controlled form for the timer's presets and alerts. Every change saves straight away; there is no Save button. */
export function FocusSettingsForm({
  value,
  onChange,
  onTimingsChange,
  onPreview,
  permission,
  busy,
  error,
  wakeLockSupported = true,
  showKeepAwake = true,
}: Props) {
  const timings: Timings = {
    focus_minutes: value.focus_minutes,
    short_break_minutes: value.short_break_minutes,
    long_break_minutes: value.long_break_minutes,
    rounds_before_long: value.rounds_before_long,
  }
  return (
    <div className="space-y-6">
      <section className="space-y-4 rounded-2xl border border-border bg-card p-6" aria-labelledby="rhythm-heading">
        <h2 id="rhythm-heading" className="text-lg font-bold">
          Rhythm
        </h2>
        <PresetPicker value={timings} preset={value.preset} onChange={onTimingsChange} disabled={busy} />
        <Row
          id="overtime"
          label="Keep the timer running after the round ends"
          hint="Extra focus time keeps counting until you press Stop and save. Your break starts then."
          checked={value.overtime_enabled}
          onChange={(v) => onChange({ overtime_enabled: v })}
        />
        <Row
          id="auto-breaks"
          label="Start breaks automatically"
          checked={value.auto_start_breaks}
          onChange={(v) => onChange({ auto_start_breaks: v })}
        />
        <Row
          id="auto-focus"
          label="Start the next round automatically after a break"
          hint="Only if you are still on this screen when the break ends."
          checked={value.auto_start_focus}
          onChange={(v) => onChange({ auto_start_focus: v })}
        />
      </section>

      <section className="space-y-4 rounded-2xl border border-border bg-card p-6" aria-labelledby="alerts-heading">
        <h2 id="alerts-heading" className="text-lg font-bold">
          Alerts
        </h2>
        <Row
          id="sound"
          label="Play a chime when a phase ends"
          checked={value.sound_enabled}
          onChange={(v) => onChange({ sound_enabled: v })}
        />
        <div className="space-y-1.5">
          <Label>Chime volume</Label>
          <div className="flex items-center gap-3">
            <Slider
              label="Chime volume"
              value={value.volume}
              min={0}
              max={100}
              step={5}
              disabled={!value.sound_enabled}
              onValueChange={(v) => onChange({ volume: v })}
            />
            <span className="w-10 text-right text-sm tabular-nums">{value.volume}</span>
            <Button type="button" variant="outline" onClick={onPreview} disabled={!value.sound_enabled}>
              Play
            </Button>
          </div>
        </div>
        <Row
          id="notify"
          label="Show a browser notification when a phase ends"
          hint="Only used while this tab is in the background."
          checked={value.notifications_enabled}
          onChange={(v) => onChange({ notifications_enabled: v })}
        />
        {permission === 'denied' ? (
          <Alert variant="info">
            <span role="status">
              Notifications are blocked in your browser. Allow them for this site in the address bar, then switch this
              on again.
            </span>
          </Alert>
        ) : null}
        {permission === 'unsupported' ? (
          <Alert variant="info">
            <span role="status">This browser does not support notifications. The tab title and chime still work.</span>
          </Alert>
        ) : null}
      </section>
      {showKeepAwake ? (
        <section className="space-y-4 rounded-2xl border border-border bg-card p-6" aria-labelledby="screen-heading">
          <h2 id="screen-heading" className="text-lg font-bold">
            Screen
          </h2>
          <Row
            id="keep-awake"
            label="Keep the screen on during focus rounds"
            hint="Stops your screen from dimming while a round runs. It only works while Artha is open and in front."
            checked={value.keep_awake}
            onChange={(v) => onChange({ keep_awake: v })}
          />
          <Row
            id="keep-awake-breaks"
            label="Also keep it on during breaks"
            checked={value.keep_awake_in_breaks}
            disabled={!value.keep_awake}
            onChange={(v) => onChange({ keep_awake_in_breaks: v })}
          />
          {!wakeLockSupported ? (
            <Alert variant="info">
              <span role="status">
                This browser cannot keep the screen on, so your screen may sleep during a round. The timer still runs.
              </span>
            </Alert>
          ) : null}
        </section>
      ) : null}
      {error ? (
        <Alert variant="error">
          <span role="alert">{error}</span>
        </Alert>
      ) : null}
    </div>
  )
}

function Row({
  id,
  label,
  hint,
  checked,
  disabled,
  onChange,
}: {
  id: string
  label: string
  hint?: string
  checked: boolean
  disabled?: boolean
  onChange: (v: boolean) => void
}) {
  return (
    <div className="flex items-start gap-3">
      <Switch id={id} checked={checked} disabled={disabled} onCheckedChange={onChange} className="mt-0.5" />
      <div>
        <label htmlFor={id} className="text-sm font-medium">
          {label}
        </label>
        {hint ? <p className="text-sm text-muted-foreground">{hint}</p> : null}
      </div>
    </div>
  )
}
