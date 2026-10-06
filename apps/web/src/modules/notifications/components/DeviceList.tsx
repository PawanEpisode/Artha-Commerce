import { Badge, Button, Smartphone, Trash2 } from '@artha/design-system'

import { formatLastSeen } from '../lib/format'
import { MAX_ACTIVE_DEVICES } from '../lib/limits'
import type { NotificationDevice } from '../lib/schemas'

const MODE_LABEL: Record<string, string> = { standalone: 'Installed app', app: 'Desktop app' }

/** The places alerts can reach, each with Remove. The device this browser registered is marked in words. */
export function DeviceList({
  devices,
  currentId,
  removingId,
  onRemove,
  now,
}: {
  devices: readonly NotificationDevice[]
  currentId: string | null
  removingId: string | null
  onRemove: (device: NotificationDevice) => void
  /** Injected so tests (and the first render) agree on what "today" is. */
  now?: Date
}) {
  if (devices.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">
        No device yet. Turn on alerts on this device above and it will appear here.
      </p>
    )
  }
  return (
    <div className="space-y-3">
      <p className="text-sm text-muted-foreground">
        {devices.length} of {MAX_ACTIVE_DEVICES} devices
      </p>
      <ul className="divide-y divide-border rounded-xl border border-border">
        {devices.map((device) => {
          const name = device.label || 'Unnamed device'
          const mode = MODE_LABEL[device.display_mode]
          return (
            <li key={device.id} className="flex flex-wrap items-center gap-x-4 gap-y-2 p-4">
              <Smartphone aria-hidden className="size-5 shrink-0 text-muted-foreground" />
              <div className="min-w-0 flex-1">
                <p className="flex flex-wrap items-center gap-2 text-sm font-medium break-words">
                  {name}
                  {device.id === currentId ? <Badge variant="accent">This device</Badge> : null}
                </p>
                <p className="text-sm text-muted-foreground">
                  {[mode, formatLastSeen(device.last_seen_at, now)].filter(Boolean).join(' · ')}
                </p>
              </div>
              <Button
                type="button"
                variant="outline"
                size="sm"
                aria-label={`Remove ${name}`}
                loading={removingId === device.id}
                onClick={() => onRemove(device)}
              >
                <Trash2 aria-hidden /> Remove
              </Button>
            </li>
          )
        })}
      </ul>
    </div>
  )
}
