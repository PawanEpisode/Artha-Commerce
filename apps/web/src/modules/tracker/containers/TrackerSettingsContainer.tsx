import { Alert, Button, DurationField, formatDuration, SelectField, Switch, TextField } from '@artha/design-system'
import { useEffect, useState } from 'react'

import { useSaveSettings } from '../hooks/useSessionActions'
import { useTrackerSettings } from '../hooks/useTrackerQueries'
import { deleteData, downloadCsv, errorMessage, exportData, resetSettings } from '../lib/api'
import { IDLE_MINUTES_MAX, IDLE_MINUTES_MIN } from '../lib/limits'
import { notify } from '../lib/notify'
import { ACTIVITY_OPTIONS, type ActivityType } from '../lib/types'
import { TrackerShell } from './TrackerShell'

function SettingsForm() {
  const q = useTrackerSettings()
  const save = useSaveSettings()
  const s = q.data
  const [idleOn, setIdleOn] = useState(true)
  const [idle, setIdle] = useState<number | null>(10)
  const [weekStart, setWeekStart] = useState<'0' | '1'>('1')
  const [activity, setActivity] = useState<ActivityType>('other')
  const [tz, setTz] = useState('')
  const [auto, setAuto] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [idleError, setIdleError] = useState<string | null>(null)
  const [confirmDelete, setConfirmDelete] = useState(false)

  useEffect(() => {
    if (!s) return
    setIdleOn(s.idle_minutes > 0)
    setIdle(s.idle_minutes || 10)
    setWeekStart(String(s.week_start) as '0' | '1')
    setActivity(s.default_activity_type)
    setTz(s.tz)
    setAuto(s.auto_capture_enabled)
  }, [s])

  const submit = () => {
    const minutes = idle ?? 0
    if (idleOn && (minutes < IDLE_MINUTES_MIN || minutes > IDLE_MINUTES_MAX)) {
      setIdleError(
        `Enter between ${formatDuration(IDLE_MINUTES_MIN, 'long')} and ${formatDuration(IDLE_MINUTES_MAX, 'long')}.`,
      )
      return
    }
    setIdleError(null)
    setError(null)
    save.mutate(
      {
        idle_minutes: idleOn ? minutes : 0,
        week_start: Number(weekStart) as 0 | 1,
        default_activity_type: activity,
        tz,
        auto_capture_enabled: auto,
      },
      {
        onSuccess: () => notify.settingsSaved(),
        onError: (e) => {
          setError(errorMessage(e))
          notify.error(e, 'Could not save your settings.')
        },
      },
    )
  }

  return (
    <>
      <header className="space-y-1">
        <h1 className="text-3xl font-extrabold">Tracker settings</h1>
        <p className="text-muted-foreground">How the timer and your reports behave.</p>
      </header>
      <form
        className="space-y-5 rounded-2xl border border-border bg-card p-6"
        onSubmit={(e) => {
          e.preventDefault()
          submit()
        }}
      >
        <div className="flex items-center gap-3">
          <Switch id="idle-on" checked={idleOn} onCheckedChange={setIdleOn} />
          <label htmlFor="idle-on" className="text-sm font-medium">
            Ask if I am still studying when I have been idle
          </label>
        </div>
        {idleOn ? (
          <DurationField
            label="Idle time before we ask"
            valueMinutes={idle}
            onChangeMinutes={setIdle}
            maxMinutes={IDLE_MINUTES_MAX}
            error={idleError ?? undefined}
            hint={`Between ${formatDuration(IDLE_MINUTES_MIN, 'long')} and ${formatDuration(IDLE_MINUTES_MAX, 'long')}.`}
          />
        ) : null}
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="grid gap-2">
            <label htmlFor="week-start" className="text-sm font-medium">
              Week starts on
            </label>
            <SelectField
              id="week-start"
              value={weekStart}
              onValueChange={(start) => setWeekStart(start as '0' | '1')}
              options={[
                { value: '1', label: 'Monday' },
                { value: '0', label: 'Sunday' },
              ]}
            />
          </div>
          <div className="grid gap-2">
            <label htmlFor="default-activity" className="text-sm font-medium">
              Default activity
            </label>
            <SelectField
              id="default-activity"
              value={activity}
              onValueChange={(next) => setActivity(next as ActivityType)}
              options={ACTIVITY_OPTIONS}
            />
          </div>
        </div>
        <TextField
          label="Time zone"
          value={tz}
          onChange={(e) => setTz(e.target.value)}
          hint="An IANA name, for example Asia/Kolkata. Days and reports follow this zone."
        />
        <div className="space-y-2 rounded-xl border border-border p-4">
          <div className="flex items-center gap-3">
            <Switch id="auto-capture" checked={auto} onCheckedChange={setAuto} />
            <label htmlFor="auto-capture" className="text-sm font-medium">
              Log time on syllabus chapter pages automatically
            </label>
          </div>
          <p className="text-sm text-muted-foreground">
            Off by default. When on, while a chapter page is open, visible and in use, we save that time as study time
            (up to 4 hours a day). We store only the chapter, the start time and the length. We never read what is on
            your screen, and a running timer or time you logged yourself always comes first. You can edit or delete any
            of it in the log, and switching this off stops it straight away.
          </p>
        </div>
        {error ? (
          <Alert variant="error">
            <span role="alert">{error}</span>
          </Alert>
        ) : null}
        <div className="flex flex-wrap gap-3">
          <Button type="submit" variant="cta" loading={save.isPending}>
            Save settings
          </Button>
          <Button
            type="button"
            variant="outline"
            onClick={() =>
              void resetSettings()
                .then(() => q.refetch())
                .then(() => notify.settingsReset())
                .catch((e: unknown) => notify.error(e, 'Could not reset your settings.'))
            }
          >
            Reset to defaults
          </Button>
        </div>
      </form>

      <section aria-labelledby="data-heading" className="space-y-3 rounded-2xl border border-border bg-card p-6">
        <h2 id="data-heading" className="text-lg font-bold">
          Your data
        </h2>
        <p className="text-sm text-muted-foreground">
          Download everything the tracker stores about you, or delete it for good. Deleting cannot be undone.
        </p>
        <div className="flex flex-wrap gap-3">
          <Button
            variant="outline"
            onClick={() => {
              notify.exportStarted('your data')
              void exportData()
                .then((d) => {
                  const url = URL.createObjectURL(new Blob([JSON.stringify(d, null, 2)], { type: 'application/json' }))
                  const a = document.createElement('a')
                  a.href = url
                  a.download = 'time-tracker-data.json'
                  a.click()
                  URL.revokeObjectURL(url)
                  notify.exportFinished('your data')
                })
                .catch((e: unknown) => notify.error(e, 'Could not download your data.'))
            }}
          >
            Download my data
          </Button>
          <Button
            variant="outline"
            onClick={() => {
              notify.exportStarted('sessions CSV')
              void downloadCsv('/tracking/sessions/export.csv', {}, 'study-sessions.csv')
                .then(() => notify.exportFinished('sessions CSV'))
                .catch((e: unknown) => notify.error(e, 'Could not download your sessions.'))
            }}
          >
            Download sessions (CSV)
          </Button>
          {confirmDelete ? (
            <Button
              variant="outline"
              className="border-destructive text-destructive"
              onClick={() =>
                void deleteData()
                  .then(() => {
                    notify.dataDeleted()
                    window.location.assign('/app/tracker')
                  })
                  .catch((e: unknown) => notify.error(e, 'Could not delete your data.'))
              }
            >
              Yes, delete all my tracker data
            </Button>
          ) : (
            <Button variant="outline" onClick={() => setConfirmDelete(true)}>
              Delete my data
            </Button>
          )}
        </div>
      </section>
    </>
  )
}

export function TrackerSettingsContainer() {
  return <TrackerShell>{() => <SettingsForm />}</TrackerShell>
}
