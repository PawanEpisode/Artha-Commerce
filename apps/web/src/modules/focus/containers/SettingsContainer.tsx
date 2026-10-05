import { Button } from '@artha/design-system'
import { Link } from '@tanstack/react-router'
import { useEffect, useRef, useState } from 'react'

import { FocusSettingsForm } from '../components/FocusSettingsForm'
import { requestNotifications } from '../hooks/useFocusAlerts'
import { useFocusSettings, useSaveFocusSettings } from '../hooks/useFocusSettings'
import { deleteData, exportData, isFeatureDisabled } from '../lib/api'
import { playChime, unlockAudio } from '../lib/chime'
import { notify } from '../lib/notify'
import type { PresetKey, Timings } from '../lib/presets'
import type { FocusSettings } from '../lib/types'
import { FocusShell } from './FocusShell'

type Permission = 'granted' | 'denied' | 'default' | 'unsupported'
const currentPermission = (): Permission =>
  typeof Notification === 'undefined' ? 'unsupported' : (Notification.permission as Permission)

function Body({ settings }: { settings: FocusSettings }) {
  const save = useSaveFocusSettings()
  const [permission, setPermission] = useState<Permission>(currentPermission)
  const [volume, setVolume] = useState(settings.volume)
  const [confirmDelete, setConfirmDelete] = useState(false)
  const timer = useRef<number | undefined>(undefined)

  useEffect(() => setVolume(settings.volume), [settings.volume])
  useEffect(() => () => window.clearTimeout(timer.current), [])

  const apply = (patch: Partial<FocusSettings>) => {
    save.mutate(patch, {
      onSuccess: () => notify.settingsSaved(),
      onError: (e) => notify.error(e, 'Could not save your settings.'),
    })
  }
  const onChange = async (patch: Partial<FocusSettings>) => {
    if (patch.volume !== undefined) {
      setVolume(patch.volume)
      window.clearTimeout(timer.current)
      timer.current = window.setTimeout(() => apply({ volume: patch.volume }), 300)
      return
    }
    if (patch.notifications_enabled) {
      const result = await requestNotifications()
      setPermission(result)
      if (result !== 'granted') {
        if (result === 'denied') notify.notificationsBlocked()
        return
      }
    }
    apply(patch)
  }
  const onTimings = (t: Timings, preset: PresetKey) => apply(preset === 'custom' ? { preset, ...t } : { preset })

  return (
    <>
      <header className="space-y-1">
        <h1 className="text-3xl font-extrabold">Focus settings</h1>
        <p className="text-muted-foreground">Your rhythm and alerts. Changes save as you make them.</p>
      </header>
      <FocusSettingsForm
        value={{ ...settings, volume }}
        onChange={(p) => void onChange(p)}
        onTimingsChange={onTimings}
        onPreview={() => {
          unlockAudio()
          playChime(volume)
        }}
        permission={permission}
        busy={save.isPending}
      />
      <section aria-labelledby="focus-data" className="space-y-3 rounded-2xl border border-border bg-card p-6">
        <h2 id="focus-data" className="text-lg font-bold">
          Your data
        </h2>
        <p className="text-sm text-muted-foreground">
          Your finished rounds are part of your study time and live in the time tracker. You can download or delete them
          from{' '}
          <Link to="/app/settings/tracker" className="font-medium underline">
            Tracker settings
          </Link>
          . Here you can download or delete the timer and its settings.
        </p>
        <div className="flex flex-wrap gap-3">
          <Button
            variant="outline"
            onClick={() => {
              notify.exportStarted()
              void exportData()
                .then((d) => {
                  const url = URL.createObjectURL(new Blob([JSON.stringify(d, null, 2)], { type: 'application/json' }))
                  const a = document.createElement('a')
                  a.href = url
                  a.download = 'focus-timer-data.json'
                  a.click()
                  URL.revokeObjectURL(url)
                  notify.exportFinished()
                })
                .catch((e: unknown) => notify.error(e, 'Could not download your timer data.'))
            }}
          >
            Download my timer data
          </Button>
          {confirmDelete ? (
            <Button
              variant="outline"
              className="border-destructive text-destructive"
              onClick={() =>
                void deleteData()
                  .then(() => {
                    notify.dataDeleted()
                    window.location.assign('/app/focus')
                  })
                  .catch((e: unknown) => notify.error(e, 'Could not delete your timer data.'))
              }
            >
              Yes, delete my timer data
            </Button>
          ) : (
            <Button variant="outline" onClick={() => setConfirmDelete(true)}>
              Delete my timer data
            </Button>
          )}
        </div>
      </section>
    </>
  )
}

export function SettingsContainer() {
  const q = useFocusSettings()
  return (
    <FocusShell
      state={q.isPending ? 'loading' : q.isError && !isFeatureDisabled(q.error) ? 'error' : 'ready'}
      disabled={isFeatureDisabled(q.error)}
      onRetry={() => void q.refetch()}
    >
      {q.data ? <Body settings={q.data} /> : null}
    </FocusShell>
  )
}
