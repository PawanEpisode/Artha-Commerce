import {
  addIsoDays,
  Alert,
  Button,
  Card,
  DatePicker,
  NumberStepper,
  Page,
  PageHeader,
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

/** One setting: the name and its hint on the left, the control on the right (stacked on a phone). */
function Row({
  id,
  title,
  hint,
  error,
  children,
}: {
  id: string
  title: string
  hint: string
  error?: string
  children: React.ReactNode
}) {
  return (
    <div className="flex flex-col gap-2 px-4 py-3 sm:flex-row sm:items-center sm:justify-between sm:gap-6">
      <div className="min-w-0 space-y-0.5">
        <label htmlFor={id} className="block text-[13px] font-medium">
          {title}
        </label>
        <p className="text-xs text-muted-foreground">{hint}</p>
        {error ? (
          <p role="alert" className="text-xs font-medium text-destructive">
            {error}
          </p>
        ) : null}
      </div>
      <div className="shrink-0">{children}</div>
    </div>
  )
}

/** A titled group of rows in one card with hairline dividers. */
function Group({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section aria-label={title} className="space-y-1.5">
      <h2 className="text-sm font-semibold">{title}</h2>
      <Card className="divide-y divide-border">{children}</Card>
    </section>
  )
}

function Vacation({ settings }: { settings: RecallSettings }) {
  const set = useSetVacation()
  const today = todayIsoDate()
  const [until, setUntil] = useState<string | null>(settings.vacation_until)
  useEffect(() => setUntil(settings.vacation_until), [settings.vacation_until])
  const active = settings.vacation_until !== null && settings.vacation_until >= today
  return (
    <section aria-labelledby="vacation-heading" className="space-y-3 rounded-lg border border-border bg-card p-4">
      <div className="space-y-0.5">
        <h2 id="vacation-heading" className="text-sm font-semibold">
          Vacation
        </h2>
        <p className="text-[13px] text-muted-foreground">
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
      <div className="flex flex-wrap gap-2">
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
        className="space-y-4"
        onSubmit={(e) => {
          e.preventDefault()
          if (Object.keys(errors).length > 0 || !dirty) return
          save.mutate(diff, { onSuccess: () => toast.success('Settings saved') })
        }}
      >
        <Group title="Daily limits">
          <Row
            id="new-per-day"
            title="New cards per day"
            hint="How many new cards join your reviews each day."
            error={errors.new_per_day}
          >
            <NumberStepper
              label="New cards per day"
              value={draft.new_per_day}
              min={0}
              max={100}
              onChange={(v) => set('new_per_day', v)}
            />
          </Row>
          <Row
            id="reviews-per-day"
            title="Reviews per day"
            hint="The most reviews you want in one day."
            error={errors.reviews_per_day}
          >
            <NumberStepper
              label="Reviews per day"
              value={draft.reviews_per_day}
              min={20}
              max={500}
              step={10}
              onChange={(v) => set('reviews_per_day', v)}
            />
          </Row>
          <Row
            id="retention"
            title="Target memory"
            hint="Higher means more reviews. 90% suits most students."
            error={errors.retention_percent}
          >
            <NumberStepper
              label="Target memory in percent"
              value={draft.retention_percent}
              min={80}
              max={97}
              onChange={(v) => set('retention_percent', v)}
            />
          </Row>
          <Row
            id="catchup"
            title="Catch-up mode"
            hint="When a backlog builds up, show the most important cards first and pause new ones."
          >
            <SelectField
              id="catchup"
              className="w-full sm:w-44"
              value={draft.catchup_mode}
              onValueChange={(v) => set('catchup_mode', v as SettingsDraft['catchup_mode'])}
              options={CATCHUP_OPTIONS}
            />
          </Row>
        </Group>

        <Group title="Behaviour">
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
        </Group>

        <Group title="Time">
          <div className="px-4 py-3">
            <TextField
              label="Time zone"
              value={draft.tz}
              error={errors.tz}
              onChange={(e) => set('tz', e.target.value)}
              hint="For example Asia/Kolkata."
              className="sm:max-w-xs"
            />
          </div>
          <Row id="day-start" title="Your day starts at" hint="Late-night study counts for the day before.">
            <NumberStepper
              label="Hour your study day starts"
              value={draft.day_start_hour}
              min={0}
              max={6}
              onChange={(v) => set('day_start_hour', v)}
            />
          </Row>
        </Group>

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
      <PageHeader title="Revision settings" description="How many cards you see and how the schedule behaves." />
      {q.isPending ? (
        <div aria-busy="true" className="space-y-3">
          <span className="sr-only" role="status">
            Loading your settings…
          </span>
          <Skeleton className="h-48 w-full" />
          <Skeleton className="h-48 w-full" />
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
        <Page width="form">
          <DataControlsContainer />
        </Page>
      </>
    )
  }
  return (
    <RecallShell width="form" tabs={false}>
      <SettingsBody />
    </RecallShell>
  )
}
