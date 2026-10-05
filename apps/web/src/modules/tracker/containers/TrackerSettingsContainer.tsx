import { Alert, Button, Select, Switch, TextField, useToast } from '@artha/design-system'
import { useEffect, useState } from 'react'

import { useSaveSettings } from '../hooks/useSessionActions'
import { useTrackerSettings } from '../hooks/useTrackerQueries'
import { deleteData, downloadCsv, errorMessage, exportData, resetSettings } from '../lib/api'
import { IDLE_MINUTES_MAX, IDLE_MINUTES_MIN } from '../lib/limits'
import { ACTIVITY_OPTIONS, type ActivityType } from '../lib/types'
import { TrackerShell } from './TrackerShell'

function SettingsForm() {
  const q = useTrackerSettings()
  const save = useSaveSettings()
  const toast = useToast()
  const s = q.data
  const [idleOn, setIdleOn] = useState(true)
  const [idle, setIdle] = useState('10')
  const [weekStart, setWeekStart] = useState<'0' | '1'>('1')
  const [activity, setActivity] = useState<ActivityType>('other')
  const [tz, setTz] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [confirmDelete, setConfirmDelete] = useState(false)

  useEffect(() => {
    if (!s) return
    setIdleOn(s.idle_minutes > 0)
    setIdle(String(s.idle_minutes || 10))
    setWeekStart(String(s.week_start) as '0' | '1')
    setActivity(s.default_activity_type)
    setTz(s.tz)
  }, [s])

  const submit = () => {
    const minutes = Number(idle)
    if (idleOn && (!Number.isInteger(minutes) || minutes < IDLE_MINUTES_MIN || minutes > IDLE_MINUTES_MAX)) {
      setError(`Idle time must be whole minutes from ${IDLE_MINUTES_MIN} to ${IDLE_MINUTES_MAX}.`)
      return
    }
    setError(null)
    save.mutate(
      {
        idle_minutes: idleOn ? minutes : 0,
        week_start: Number(weekStart) as 0 | 1,
        default_activity_type: activity,
        tz,
      },
      { onSuccess: () => toast.show({ message: 'Settings saved.' }), onError: (e) => setError(errorMessage(e)) },
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
          <TextField
            label="Idle time (minutes)"
            type="number"
            inputMode="numeric"
            value={idle}
            onChange={(e) => setIdle(e.target.value)}
            hint={`Between ${IDLE_MINUTES_MIN} and ${IDLE_MINUTES_MAX}.`}
          />
        ) : null}
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="grid gap-2">
            <label htmlFor="week-start" className="text-sm font-medium">
              Week starts on
            </label>
            <Select id="week-start" value={weekStart} onChange={(e) => setWeekStart(e.target.value as '0' | '1')}>
              <option value="1">Monday</option>
              <option value="0">Sunday</option>
            </Select>
          </div>
          <div className="grid gap-2">
            <label htmlFor="default-activity" className="text-sm font-medium">
              Default activity
            </label>
            <Select
              id="default-activity"
              value={activity}
              onChange={(e) => setActivity(e.target.value as ActivityType)}
            >
              {ACTIVITY_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </Select>
          </div>
        </div>
        <TextField
          label="Time zone"
          value={tz}
          onChange={(e) => setTz(e.target.value)}
          hint="An IANA name, for example Asia/Kolkata. Days and reports follow this zone."
        />
        {error ? (
          <Alert variant="error">
            <span role="alert">{error}</span>
          </Alert>
        ) : null}
        <div className="flex flex-wrap gap-3">
          <Button type="submit" disabled={save.isPending}>
            Save settings
          </Button>
          <Button type="button" variant="ghost" onClick={() => void resetSettings().then(() => q.refetch())}>
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
            onClick={() =>
              void exportData().then((d) => {
                const url = URL.createObjectURL(new Blob([JSON.stringify(d, null, 2)], { type: 'application/json' }))
                const a = document.createElement('a')
                a.href = url
                a.download = 'time-tracker-data.json'
                a.click()
                URL.revokeObjectURL(url)
              })
            }
          >
            Download my data
          </Button>
          <Button
            variant="outline"
            onClick={() => void downloadCsv('/tracking/sessions/export.csv', {}, 'study-sessions.csv')}
          >
            Download sessions (CSV)
          </Button>
          {confirmDelete ? (
            <Button
              variant="outline"
              className="border-destructive text-destructive"
              onClick={() => void deleteData().then(() => window.location.assign('/app/tracker'))}
            >
              Yes, delete all my tracker data
            </Button>
          ) : (
            <Button variant="ghost" onClick={() => setConfirmDelete(true)}>
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
