import {
  Alert,
  Button,
  Card,
  EmptyState,
  Page,
  PageHeader,
  PresetChips,
  SegmentedControl,
  Skeleton,
  Sparkles,
  Switch,
  toast,
} from '@artha/design-system'
import { Link } from '@tanstack/react-router'
import { useEffect, useState } from 'react'

import { useOnline } from '../hooks/useOnline'
import { useRebuildToday, useSaveTodaySettings } from '../hooks/useSaveTodaySettings'
import { useTodayFlag } from '../hooks/useTodayFlag'
import { useTodaySettings } from '../hooks/useTodayQueries'
import { errorMessage, isFeatureDisabled } from '../lib/api'
import {
  DEFAULT_SETTINGS,
  FOCUS_OPTIONS,
  focusFromValue,
  focusValue,
  kindLabel,
  listedKinds,
  MINUTE_PRESETS,
} from '../lib/settings'
import type { TodaySettings } from '../lib/types'

const Shell = ({ children }: { children: React.ReactNode }) => <Page width="form">{children}</Page>

/** One settings row: label and hint on the left, the control on the right. */
function Row({ id, title, hint, children }: { id: string; title: string; hint?: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-2 p-4 sm:flex-row sm:items-center sm:justify-between sm:gap-4">
      <div className="min-w-0 space-y-0.5">
        <label htmlFor={id} className="text-[13px] font-medium">
          {title}
        </label>
        {hint ? (
          <p id={`${id}-hint`} className="text-xs text-muted-foreground">
            {hint}
          </p>
        ) : null}
      </div>
      <div className="min-w-0 sm:shrink-0">{children}</div>
    </div>
  )
}

function Form({ saved }: { saved: TodaySettings }) {
  const online = useOnline()
  const save = useSaveTodaySettings(saved)
  const rebuild = useRebuildToday()
  const [draft, setDraft] = useState<TodaySettings>(saved)
  const [error, setError] = useState<string | null>(null)
  const [dirty, setDirty] = useState(false)
  const [changedBudget, setChangedBudget] = useState(false)
  useEffect(() => {
    if (!dirty) setDraft(saved)
  }, [saved, dirty])

  const set = <K extends keyof TodaySettings>(key: K, value: TodaySettings[K]) => {
    setDraft((d) => ({ ...d, [key]: value }))
    setDirty(true)
  }
  const toggleKind = (kind: string, shown: boolean) =>
    set(
      'disabled_kinds',
      shown ? draft.disabled_kinds.filter((k) => k !== kind) : [...new Set([...draft.disabled_kinds, kind])],
    )

  const submit = (values: TodaySettings, message: string) => {
    setError(null)
    save.mutate(values, {
      onSuccess: () => {
        setDirty(false)
        setChangedBudget(true)
        toast.success(message)
      },
      onError: (e) => setError(errorMessage(e, 'We could not save your settings. Please try again.')),
    })
  }

  const preset = draft.minutes_per_day !== null && MINUTE_PRESETS.some((m) => m === draft.minutes_per_day)
  return (
    <>
      <PageHeader title="Today settings" description="How much we plan for you each day, and what we leave out." />
      {!online ? (
        <Alert variant="info">
          You are offline, so settings cannot be changed right now. Connect to the internet and come back.
        </Alert>
      ) : null}
      {error ? <Alert variant="error">{error}</Alert> : null}
      <form
        className="space-y-3"
        onSubmit={(e) => {
          e.preventDefault()
          submit(draft, 'Settings saved')
        }}
      >
        <fieldset disabled={!online} className="min-w-0 border-0 p-0">
          <Card className="divide-y">
            <div className="space-y-2 p-4">
              <p id="minutes-label" className="text-[13px] font-medium">
                Minutes per day
              </p>
              <PresetChips
                label="Minutes per day"
                value={draft.minutes_per_day === null ? 'auto' : preset ? String(draft.minutes_per_day) : null}
                onValueChange={(v) => set('minutes_per_day', v === 'auto' ? null : Number(v))}
                options={[
                  { value: 'auto', label: 'Automatic', description: 'From your exam date' },
                  ...MINUTE_PRESETS.map((m) => ({ value: String(m), label: `${m} min` })),
                ]}
              />
              <p className="text-xs text-muted-foreground">
                Automatic uses your exam date and study hours. A fixed number is the most we plan, never a promise to
                fill it.
              </p>
            </div>

            <div className="space-y-2 p-4">
              <p className="text-[13px] font-medium">Papers to focus on each day</p>
              <SegmentedControl
                label="Papers to focus on each day"
                value={focusValue(draft.focus_papers)}
                onValueChange={(v) => set('focus_papers', focusFromValue(v))}
                options={FOCUS_OPTIONS.map((o) => ({ value: o, label: o === 'auto' ? 'Auto' : o }))}
              />
              <p className="text-xs text-muted-foreground">
                The papers take turns, so each one comes round within a few days.
              </p>
            </div>

            <fieldset className="border-0 p-4">
              <legend className="mb-2 text-[13px] font-medium">Kinds of task to show</legend>
              <div className="grid gap-x-4 gap-y-2 sm:grid-cols-2">
                {listedKinds(draft.disabled_kinds).map((kind) => (
                  <div key={kind} className="flex items-center gap-2.5">
                    <Switch
                      id={`kind-${kind}`}
                      checked={!draft.disabled_kinds.includes(kind)}
                      onCheckedChange={(on) => toggleKind(kind, on)}
                    />
                    <label htmlFor={`kind-${kind}`} className="text-[13px]">
                      {kindLabel(kind)}
                    </label>
                  </div>
                ))}
              </div>
            </fieldset>

            <Row id="show-tomorrow" title="Show a preview of tomorrow" hint="After 6 pm, or once today is finished.">
              <Switch
                id="show-tomorrow"
                aria-describedby="show-tomorrow-hint"
                checked={draft.show_tomorrow}
                onCheckedChange={(on) => set('show_tomorrow', on)}
              />
            </Row>
            <Row
              id="celebrate"
              title="Celebrate a finished day"
              hint="A short animation, off when your device asks for less motion."
            >
              <Switch
                id="celebrate"
                aria-describedby="celebrate-hint"
                checked={draft.celebrate}
                onCheckedChange={(on) => set('celebrate', on)}
              />
            </Row>

            <div className="space-y-2 p-4">
              <p className="text-[13px] font-medium">Lite mode</p>
              <SegmentedControl
                label="Lite mode"
                value={draft.lite_mode}
                onValueChange={(v) => set('lite_mode', v)}
                options={[
                  { value: 'auto', label: 'Auto' },
                  { value: 'on', label: 'On' },
                  { value: 'off', label: 'Off' },
                ]}
              />
              <p className="text-xs text-muted-foreground">
                No animation or charts, and less data. Auto turns it on when your phone is saving data or the connection
                is slow.
              </p>
            </div>
          </Card>
        </fieldset>

        <div className="flex flex-wrap gap-2">
          <Button type="submit" disabled={!online || save.isPending || !dirty}>
            {save.isPending ? 'Saving' : 'Save settings'}
          </Button>
          <Button
            type="button"
            variant="outline"
            disabled={!online || save.isPending}
            onClick={() => submit(DEFAULT_SETTINGS, 'Settings reset to the defaults')}
          >
            Reset to defaults
          </Button>
        </div>
      </form>
      {changedBudget ? (
        <Alert variant="info">
          <p>New settings apply from tomorrow's plan. To use them for today as well, update today's list.</p>
          <Button
            className="mt-3"
            variant="outline"
            size="sm"
            disabled={!online || rebuild.isPending}
            onClick={() => rebuild.mutate()}
          >
            {rebuild.isPending ? 'Updating' : "Update today's plan"}
          </Button>
        </Alert>
      ) : null}
      <p className="text-[13px]">
        <Link to="/app/today" className="font-medium underline underline-offset-4">
          Back to Today
        </Link>
      </p>
    </>
  )
}

/** /app/settings/today: minutes per day, focus papers, hidden kinds, tomorrow preview, celebration, lite mode, reset (PRD 7.3). */
export function TodaySettingsContainer() {
  const enabled = useTodayFlag()
  const settings = useTodaySettings(enabled)

  if (!enabled || isFeatureDisabled(settings.error)) {
    return (
      <Shell>
        <EmptyState
          icon={<Sparkles aria-hidden />}
          title="Today is not available yet"
          description="We are rolling it out gradually. Please check back soon."
        />
      </Shell>
    )
  }
  if (settings.isPending) {
    return (
      <Shell>
        <div role="status" aria-label="Loading your settings" className="space-y-3">
          <Skeleton className="h-8 w-1/2" />
          <Skeleton className="h-64 w-full" />
        </div>
      </Shell>
    )
  }
  if (settings.isError || !settings.data) {
    return (
      <Shell>
        <Alert variant="error">
          <p>We could not load your settings.</p>
          <Button className="mt-3" variant="outline" size="sm" onClick={() => void settings.refetch()}>
            Try again
          </Button>
        </Alert>
      </Shell>
    )
  }
  return (
    <Shell>
      <Form saved={settings.data} />
    </Shell>
  )
}
