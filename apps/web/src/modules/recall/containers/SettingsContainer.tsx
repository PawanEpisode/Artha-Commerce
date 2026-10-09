import {
  addIsoDays,
  Alert,
  Button,
  Container,
  DatePicker,
  NumberStepper,
  SelectField,
  Skeleton,
  Switch,
  TextField,
  toast,
  todayIsoDate,
} from '@artha/design-system'
import { useEffect, useState } from 'react'

import { LoadError, RecallShell, RecallUnavailable } from '../components/RecallShell'
import { useRecallEnabled } from '../hooks/useRecallBasics'
import { useSaveSettings, useSettings, useSetVacation } from '../hooks/useSettings'
import { errorText } from '../lib/errors'
import type { RecallSettings } from '../lib/schemas'
import { CATCHUP_OPTIONS, changes, draftOf, type SettingsDraft, VACATION_MAX_DAYS, validate } from '../lib/settingsForm'
import { DataControlsContainer } from './DataControlsContainer'

function Row({ id, title, hint, children }: { id: string; title: string; hint: string; children: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-4">
      <label htmlFor={id} className="space-y-0.5">
        <span className="block text-sm font-medium">{title}</span>
        <span className="block text-sm text-muted-foreground">{hint}</span>
      </label>
      {children}
    </div>
  )
}

function Vacation({ settings }: { settings: RecallSettings }) {
  const set = useSetVacation()
  const today = todayIsoDate()
  const [until, setUntil] = useState<string | null>(settings.vacation_until)
  useEffect(() => setUntil(settings.vacation_until), [settings.vacation_until])
  const active = settings.vacation_until !== null && settings.vacation_until >= today
  return (
    <section aria-labelledby="vacation-heading" className="space-y-4 rounded-2xl border border-border bg-card p-6">
      <div className="space-y-1">
        <h2 id="vacation-heading" className="font-display text-lg font-bold">
          Vacation
        </h2>
        <p className="text-sm text-muted-foreground">
          Pause reviews for up to {VACATION_MAX_DAYS} days. Your streak is kept and cards do not pile up as overdue.
        </p>
      </div>
      <DatePicker
        label="Reviews resume after"
        hint={active ? 'You are on vacation now.' : 'Pick the last day of your break.'}
        value={until}
        onValueChange={setUntil}
        min={today}
        max={addIsoDays(today, VACATION_MAX_DAYS)}
      />
      <div className="flex flex-wrap gap-3">
        <Button
          disabled={set.isPending || until === null || until === settings.vacation_until}
          onClick={() => set.mutate(until, { onSuccess: () => toast.success('Vacation saved') })}
        >
          Save vacation
        </Button>
        {active ? (
          <Button
            variant="outline"
            disabled={set.isPending}
            onClick={() => set.mutate(null, { onSuccess: () => toast.success('Vacation ended') })}
          >
            End vacation now
          </Button>
        ) : null}
      </div>
      {set.isError ? <Alert variant="error">{errorText(set.error, 'Could not save your vacation.')}</Alert> : null}
    </section>
  )
}

function Form({ settings }: { settings: RecallSettings }) {
  const save = useSaveSettings()
  const [draft, setDraft] = useState<SettingsDraft>(() => draftOf(settings))
  useEffect(() => setDraft(draftOf(settings)), [settings])
  const errors = validate(draft)
  const diff = changes(settings, draft)
  const dirty = Object.keys(diff).length > 0
  const set = <K extends keyof SettingsDraft>(key: K, value: SettingsDraft[K]) =>
    setDraft((d) => ({ ...d, [key]: value }))

  return (
    <>
      <form
        className="space-y-5 rounded-2xl border border-border bg-card p-6"
        onSubmit={(e) => {
          e.preventDefault()
          if (Object.keys(errors).length > 0 || !dirty) return
          save.mutate(diff, { onSuccess: () => toast.success('Settings saved') })
        }}
      >
        <Row id="new-per-day" title="New cards per day" hint="How many new cards join your reviews each day.">
          <NumberStepper
            label="New cards per day"
            value={draft.new_per_day}
            min={0}
            max={100}
            onChange={(v) => set('new_per_day', v)}
          />
        </Row>
        {errors.new_per_day ? (
          <p role="alert" className="text-sm font-medium text-destructive">
            {errors.new_per_day}
          </p>
        ) : null}
        <Row id="reviews-per-day" title="Reviews per day" hint="The most reviews you want in one day.">
          <NumberStepper
            label="Reviews per day"
            value={draft.reviews_per_day}
            min={20}
            max={500}
            step={10}
            onChange={(v) => set('reviews_per_day', v)}
          />
        </Row>
        {errors.reviews_per_day ? (
          <p role="alert" className="text-sm font-medium text-destructive">
            {errors.reviews_per_day}
          </p>
        ) : null}
        <Row id="retention" title="Target memory" hint="Higher means more reviews. 90% suits most students.">
          <NumberStepper
            label="Target memory in percent"
            value={draft.retention_percent}
            min={80}
            max={97}
            onChange={(v) => set('retention_percent', v)}
          />
        </Row>
        {errors.retention_percent ? (
          <p role="alert" className="text-sm font-medium text-destructive">
            {errors.retention_percent}
          </p>
        ) : null}
        <div className="grid gap-2">
          <label htmlFor="catchup" className="text-sm font-medium">
            Catch-up mode
          </label>
          <SelectField
            id="catchup"
            value={draft.catchup_mode}
            onValueChange={(v) => set('catchup_mode', v as SettingsDraft['catchup_mode'])}
            options={CATCHUP_OPTIONS}
          />
          <p className="text-sm text-muted-foreground">
            When a backlog builds up, show the most important cards first and pause new ones.
          </p>
        </div>
        <Row id="interleave" title="Mix subjects" hint="Alternate between subjects instead of one block at a time.">
          <Switch id="interleave" checked={draft.interleave} onCheckedChange={(v) => set('interleave', v)} />
        </Row>
        <Row id="bury" title="Space out related cards" hint="Hold back cards made from the same note until tomorrow.">
          <Switch id="bury" checked={draft.bury_siblings} onCheckedChange={(v) => set('bury_siblings', v)} />
        </Row>
        <Row
          id="gestures"
          title="Swipe gestures"
          hint="Swipe left for Again and right for Good. The buttons always work."
        >
          <Switch id="gestures" checked={draft.gestures} onCheckedChange={(v) => set('gestures', v)} />
        </Row>
        <Row id="intervals" title="Show next review time" hint="Show when each answer would bring the card back.">
          <Switch id="intervals" checked={draft.show_intervals} onCheckedChange={(v) => set('show_intervals', v)} />
        </Row>
        <Row id="consent" title="Help improve the scheduler" hint="Share anonymous review timings, never card text.">
          <Switch
            id="consent"
            checked={draft.improve_scheduler_consent}
            onCheckedChange={(v) => set('improve_scheduler_consent', v)}
          />
        </Row>
        <div className="grid gap-4 sm:grid-cols-2">
          <TextField
            label="Time zone"
            value={draft.tz}
            error={errors.tz}
            onChange={(e) => set('tz', e.target.value)}
            hint="For example Asia/Kolkata."
          />
          <div className="grid gap-2">
            <span className="text-sm font-medium" id="day-start-label">
              Your day starts at
            </span>
            <NumberStepper
              label="Hour your study day starts"
              value={draft.day_start_hour}
              min={0}
              max={6}
              onChange={(v) => set('day_start_hour', v)}
            />
            <p className="text-sm text-muted-foreground">Late-night study counts for the day before.</p>
          </div>
        </div>
        {save.isError ? <Alert variant="error">{errorText(save.error, 'Could not save your settings.')}</Alert> : null}
        <Button
          type="submit"
          disabled={!dirty || Object.keys(errors).length > 0 || save.isPending}
          aria-busy={save.isPending}
        >
          Save settings
        </Button>
      </form>
      <Vacation settings={settings} />
    </>
  )
}

function SettingsBody() {
  const q = useSettings()
  return (
    <>
      <header className="space-y-1">
        <h1 className="text-3xl font-extrabold">Revision settings</h1>
        <p className="text-muted-foreground">How many cards you see and how the schedule behaves.</p>
      </header>
      {q.isPending ? (
        <div aria-busy="true" className="space-y-4">
          <span className="sr-only" role="status">
            Loading your settings…
          </span>
          <Skeleton className="h-96 w-full" />
        </div>
      ) : q.isError || !q.data ? (
        <LoadError what="your settings" onRetry={() => void q.refetch()} />
      ) : (
        <Form settings={q.data} />
      )}
      <DataControlsContainer />
    </>
  )
}

/**
 * With the feature switched off the student still reaches "your data" (export and erase must never wait on a rollout
 * flag, D4), under the usual "not available yet" message.
 */
export function SettingsContainer() {
  const enabled = useRecallEnabled()
  if (!enabled) {
    return (
      <>
        <RecallUnavailable />
        <Container className="max-w-3xl pb-14">
          <DataControlsContainer />
        </Container>
      </>
    )
  }
  return (
    <RecallShell>
      <SettingsBody />
    </RecallShell>
  )
}
