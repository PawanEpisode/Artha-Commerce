import { Button } from '@artha/design-system'

import { useRefreshAnalytics } from '../hooks/useAnalytics'

interface FreshnessChipProps {
  lastCalculatedAt?: string
  factsVersion?: number
}

export function FreshnessChip({ lastCalculatedAt }: FreshnessChipProps) {
  const { mutate: refresh, isPending } = useRefreshAnalytics()

  const formatTimestamp = (ts?: string) => {
    if (!ts) return 'Up to date'
    try {
      const d = new Date(ts)
      return `Updated ${d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`
    } catch {
      return 'Up to date'
    }
  }

  return (
    <div className="text-text-subtle flex items-center gap-2 text-xs">
      <span>{formatTimestamp(lastCalculatedAt)}</span>
      <Button variant="ghost" size="sm" className="h-6 px-2 text-xs" onClick={() => refresh(50)} loading={isPending}>
        Sync
      </Button>
    </div>
  )
}
