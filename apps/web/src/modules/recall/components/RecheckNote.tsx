import { Badge, Button } from '@artha/design-system'

import { recheckHelp, recheckLabel } from '../lib/updates'

interface Props {
  reason: string | null
  pending?: boolean
  offline?: boolean
  onConfirm: () => void
}

/** "Updated, please re-check" with the one button that clears it. Memory is never touched by it. */
export function RecheckNote({ reason, pending, offline, onConfirm }: Props) {
  return (
    <div className="space-y-2 rounded-lg border border-input bg-secondary p-3 text-[13px]">
      <p className="flex flex-wrap items-center gap-2">
        <Badge variant="highlight">{recheckLabel(reason)}</Badge>
      </p>
      <p className="text-muted-foreground">{recheckHelp(reason)}</p>
      <Button size="sm" variant="outline" loading={pending} disabled={offline} onClick={onConfirm}>
        Still correct
      </Button>
      {offline ? <p className="text-xs text-muted-foreground">Connect to the internet to confirm this.</p> : null}
    </div>
  )
}
