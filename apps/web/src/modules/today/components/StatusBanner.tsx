import { Alert, Button, CloudOff } from '@artha/design-system'

import type { Banner } from '../lib/offline'
import { formatDay } from '../lib/time'

const changes = (n: number) => (n === 1 ? '1 change' : `${n} changes`)

/**
 * The one line about the connection and the plan's age (PRD 7.3: Offline, Reconnect, Stale cache, Updating). `previous_day` also means
 * the actions are off: the screen passes `readOnly` to the rows when it shows that banner.
 */
export function StatusBanner({
  banner,
  planDate,
  onRefresh,
}: {
  banner: Banner
  planDate: string
  onRefresh?: () => void
}) {
  switch (banner.kind) {
    case 'none':
      return null
    case 'updating':
      return (
        <p role="status" className="text-xs text-muted-foreground">
          Updating
        </p>
      )
    case 'offline':
      return (
        <Alert variant="info" data-banner="offline">
          <p className="flex items-center gap-2 font-medium">
            <CloudOff aria-hidden className="size-4" />
            Offline: your changes are saved on this device
          </p>
          {banner.waiting > 0 ? (
            <p className="mt-1 text-muted-foreground">{changes(banner.waiting)} waiting to sync.</p>
          ) : null}
        </Alert>
      )
    case 'syncing':
      return (
        <Alert variant="info" data-banner="syncing">
          Back online, syncing {changes(banner.waiting)}
        </Alert>
      )
    case 'stale':
      return (
        <Alert variant="info" data-banner="stale">
          <div className="flex flex-wrap items-center gap-3">
            <span>{banner.label}.</span>
            {onRefresh ? (
              <Button size="sm" variant="outline" onClick={onRefresh}>
                Refresh
              </Button>
            ) : null}
          </div>
        </Alert>
      )
    case 'previous_day':
      return (
        <Alert variant="info" data-banner="previous-day">
          Plan from {formatDay(planDate)}. Connect to get today's.
        </Alert>
      )
  }
}

/** "A new day started. Show today": the page was open across the student's midnight. In-flight actions are not discarded. */
export function DayRolloverBar({ onShow }: { onShow: () => void }) {
  return (
    <Alert variant="info" data-banner="rollover">
      <div className="flex flex-wrap items-center gap-3">
        <span>A new day started.</span>
        <Button size="sm" onClick={onShow}>
          Show today
        </Button>
      </div>
    </Alert>
  )
}
