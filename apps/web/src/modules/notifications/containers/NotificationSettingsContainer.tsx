import { Alert, Button } from '@artha/design-system'
import { useQueryClient } from '@tanstack/react-query'
import { useMemo } from 'react'

import { CategoryGrid } from '../components/CategoryGrid'
import { DeviceList } from '../components/DeviceList'
import { NudgeForm } from '../components/NudgeForm'
import { PermissionCard } from '../components/PermissionCard'
import { QuietHoursForm } from '../components/QuietHoursForm'
import { SwitchRow } from '../components/SwitchRow'
import { TestPushControl } from '../components/TestPushControl'
import { TimeZoneField } from '../components/TimeZoneField'
import {
  useDevices,
  useNotificationCategories,
  useNotificationSettings,
  useRemoveDevice,
  useSaveNotificationSettings,
  useSetPreference,
} from '../hooks/useNotificationQueries'
import { usePushCapability } from '../hooks/usePushCapability'
import { usePushEnable } from '../hooks/usePushEnable'
import { useRegistrationRefresh } from '../hooks/useRegistrationRefresh'
import { useTestPush } from '../hooks/useTestPush'
import { isNotificationsDisabled } from '../lib/api'
import { rememberedDeviceId } from '../lib/deviceMemory'
import { notificationKeys } from '../lib/keys'
import { notify } from '../lib/notify'
import type { NotificationSettings, SettingsPatch } from '../lib/schemas'
import { browserTimeZone, proposeTimeZone, timeZoneOptions } from '../lib/timezone'
import { DigestContainer } from './DigestContainer'
import { NotificationsShell } from './NotificationsShell'

const Card = ({ id, title, children }: { id: string; title: string; children: React.ReactNode }) => (
  <section aria-labelledby={id} className="space-y-4 rounded-2xl border border-border bg-card p-6">
    <h2 id={id} className="text-lg font-bold">
      {title}
    </h2>
    {children}
  </section>
)

function Body({ settings }: { settings: NotificationSettings }) {
  const qc = useQueryClient()
  const save = useSaveNotificationSettings()
  const categories = useNotificationCategories()
  const setPreference = useSetPreference()
  const devices = useDevices()
  const removeDevice = useRemoveDevice()
  const capability = usePushCapability()
  const { enable, busy: enabling } = usePushEnable('settings')
  const currentId = rememberedDeviceId()
  const test = useTestPush(devices.data, currentId, () => void devices.refetch())

  useRegistrationRefresh(capability.view.kind === 'active')

  const apply = (patch: SettingsPatch) =>
    save.mutate(patch, {
      onSuccess: () => notify.saved(),
      onError: (error) => notify.error(error, 'Could not save your settings.'),
    })

  const onEnable = async () => {
    if (!capability.environment) return
    const outcome = await enable(capability.environment)
    notify.enableOutcome(outcome)
    await capability.refresh()
    await Promise.all([
      qc.invalidateQueries({ queryKey: notificationKeys.devices }),
      qc.invalidateQueries({ queryKey: notificationKeys.settings }),
    ])
  }

  const zone = browserTimeZone()
  const zoneOptions = useMemo(() => timeZoneOptions(settings.timezone, zone), [settings.timezone, zone])
  const environment = capability.environment

  return (
    <>
      <PermissionCard
        view={capability.view}
        browser={environment?.browser ?? 'other'}
        platform={environment?.platform ?? 'other'}
        busy={enabling}
        onEnable={() => void onEnable()}
        onCheckAgain={() => void capability.refresh()}
      />

      <DigestContainer place="settings" />

      <Card id="master-heading" title="Alerts">
        <SwitchRow
          id="push-master"
          label="Send alerts to my devices"
          hint="Turn this off to pause every push alert on every device. Your choices below are kept."
          checked={settings.push_master}
          onChange={(value) => apply({ push_master: value })}
        />
        {settings.push_master ? null : (
          <Alert variant="info">
            <span role="status">
              Push alerts are paused. Nothing will be sent to your devices until you turn this on.
            </span>
          </Alert>
        )}
      </Card>

      <Card id="categories-heading" title="What to tell me about">
        {categories.isPending ? (
          <p role="status" className="text-sm text-muted-foreground">
            Loading your choices…
          </p>
        ) : categories.isError ? (
          <Alert variant="error">
            <span className="flex flex-wrap items-center gap-3">
              We could not load your choices.
              <Button variant="outline" onClick={() => void categories.refetch()}>
                Try again
              </Button>
            </span>
          </Alert>
        ) : (
          <>
            <CategoryGrid
              categories={categories.data}
              onChange={(change) =>
                setPreference.mutate(change, {
                  onSuccess: () => notify.saved(),
                  onError: (error) => notify.error(error, 'Could not save that choice.'),
                })
              }
            />
            <p className="text-sm text-muted-foreground">
              Inbox and email choices are saved now and start working as those features arrive.
            </p>
          </>
        )}
      </Card>

      <Card id="when-heading" title="When">
        <TimeZoneField
          value={settings.timezone}
          options={zoneOptions}
          proposal={proposeTimeZone(settings.timezone, zone)}
          onChange={(timezone) => apply({ timezone })}
        />
        <QuietHoursForm
          enabled={settings.quiet_enabled}
          start={settings.quiet_start}
          end={settings.quiet_end}
          onChange={apply}
        />
        <NudgeForm
          enabled={settings.nudge_enabled}
          time={settings.nudge_time}
          tone={settings.nudge_tone}
          onChange={apply}
        />
      </Card>

      <Card id="devices-heading" title="Your devices">
        {devices.isPending ? (
          <p role="status" className="text-sm text-muted-foreground">
            Loading your devices…
          </p>
        ) : devices.isError ? (
          <Alert variant="error">
            <span className="flex flex-wrap items-center gap-3">
              We could not load your devices.
              <Button variant="outline" onClick={() => void devices.refetch()}>
                Try again
              </Button>
            </span>
          </Alert>
        ) : (
          <DeviceList
            devices={devices.data}
            currentId={currentId}
            removingId={removeDevice.isPending ? (removeDevice.variables?.id ?? null) : null}
            onRemove={(device) =>
              removeDevice.mutate(device, {
                onSuccess: () => {
                  notify.deviceRemoved()
                  void capability.refresh()
                },
                onError: (error) => notify.error(error, 'Could not remove that device.'),
              })
            }
          />
        )}
        <TestPushControl
          status={test.status}
          canSend={test.canSend}
          hasDevice={test.target !== null}
          onSend={test.send}
        />
      </Card>
    </>
  )
}

/** `/app/settings/notifications`: master switch, categories, schedule, devices and the test button. */
export function NotificationSettingsContainer() {
  const query = useNotificationSettings()
  const disabled = isNotificationsDisabled(query.error)
  return (
    <NotificationsShell
      state={query.isPending ? 'loading' : query.isError && !disabled ? 'error' : 'ready'}
      disabled={disabled}
      onRetry={() => void query.refetch()}
    >
      {query.data ? <Body settings={query.data} /> : null}
    </NotificationsShell>
  )
}
