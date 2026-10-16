import { Button, PageHeader } from '@artha/design-system'
import { Link } from '@tanstack/react-router'
import { useEffect, useRef, useState } from 'react'

import { isWakeLockSupported } from '~/modules/keepawake'
import { useFeatureFlag } from '~/modules/observability'

import { FocusSettingsForm } from '../components/FocusSettingsForm'
import { requestNotifications } from '../hooks/useFocusAlerts'
import { useFocusSettings, useSaveFocusSettings } from '../hooks/useFocusSettings'
import { deleteData, exportData, isFeatureDisabled } from '../lib/api'
import { playChime, unlockAudio } from '../lib/chime'
import { notify } from '../lib/notify'
import { isDocumentPipSupported } from '../lib/pip'
import type { PresetKey, Timings } from '../lib/presets'
import type { FocusSettings } from '../lib/types'
import { FocusShell } from './FocusShell'

type Permission = 'granted' | 'denied' | 'default' | 'unsupported'
const currentPermission = (): Permission =>
  typeof Notification === 'undefined' ? 'unsupported' : (Notification.permission as Permission)

function Body({ settings }: { settings: FocusSettings }) {
  const save = useSaveFocusSettings()
  const keepAwakeFlag = useFeatureFlag('keep_awake')
  const floatingTimerFlag = useFeatureFlag('floating_timer')
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
      <PageHeader title="Focus settings" description="Your rhythm and alerts. Changes save as you make them." />
      <FocusSettingsForm
        value={{ ...settings, volume }}
        onChange={(p) => void onChange(p)}
        onTimingsChange={onTimings}
        onPreview={() => {
          unlockAudio()
          playChime(volume)
        }}
        permission={permission}
        wakeLockSupported={isWakeLockSupported()}
        showKeepAwake={keepAwakeFlag}
        showPopOut={floatingTimerFlag}
        popoutSupported={isDocumentPipSupported()}
        busy={save.isPending}
      />
      <section aria-labelledby="focus-data" className="space-y-2 rounded-lg border border-border bg-card p-4">
        <h2 id="focus-data" className="text-sm font-semibold">
          Your data
        </h2>
        <p className="text-[13px] text-muted-foreground">
          Your finished rounds are part of your study time and live in the time tracker. You can download or delete them
          from{' '}
          <Link to="/app/settings/tracker" className="font-medium underline">
            Tracker settings
          </Link>
          . Here you can download or delete the timer and its settings.
        </p>
        <div className="flex flex-wrap gap-2">
          <Button
            variant="outline"
            size="sm"
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
              size="sm"
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
            <Button variant="outline" size="sm" onClick={() => setConfirmDelete(true)}>
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
      width="form"
      tabs={false}
    >
      {q.data ? <Body settings={q.data} /> : null}
    </FocusShell>
  )
}
