import { Moon, Sun } from '@artha/design-system'

import { keepAwakeLabel, type KeepAwakeStatus } from '../lib/wakeLock'

/**
 * Says whether the screen will stay on (FR-K4). The polite live region is always present so a change is spoken; the
 * chip inside it is hidden when the browser cannot hold the screen or nothing asks it to. The state is carried by the
 * words and the icon, never by colour alone.
 */
export function KeepAwakeChip({ status }: { status: KeepAwakeStatus }) {
  const label = keepAwakeLabel(status)
  const Icon = status === 'held' ? Sun : Moon
  return (
    <div role="status" aria-live="polite" data-testid="keep-awake" className="empty:hidden">
      {label ? (
        <span
          data-status={status}
          className="inline-flex items-center gap-1.5 rounded-full border border-border bg-card px-3 py-1 text-sm font-medium text-foreground"
        >
          <Icon className="size-4" aria-hidden="true" />
          {label}
        </span>
      ) : null}
    </div>
  )
}
