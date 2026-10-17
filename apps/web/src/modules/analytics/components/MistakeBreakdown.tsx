import { Card, ProgressBar, Skeleton } from '@artha/design-system'

import type { MistakesData } from '../lib/types'

interface MistakeBreakdownProps {
  data?: MistakesData
  isLoading?: boolean
}

export function MistakeBreakdown({ data, isLoading }: MistakeBreakdownProps) {
  if (isLoading || !data) {
    return <Skeleton className="h-48 w-full rounded-xl" />
  }

  const total = data.total_tagged_mistakes ?? data.items?.reduce((sum, i) => sum + i.count, 0) ?? 0
  const items = data.items ?? []

  return (
    <Card className="space-y-4 p-5">
      <div className="flex items-start justify-between">
        <div>
          <h3 className="text-text text-base font-semibold">Mistake Pattern Analysis</h3>
          <p className="text-text-subtle text-xs">Root-cause breakdown from self-tagged practice errors</p>
        </div>
        <div className="text-text-subtle text-xs font-medium">{total} tagged mistakes</div>
      </div>

      {items.length === 0 ? (
        <div className="text-text-subtle py-6 text-center text-xs">
          No tagged mistakes recorded. Tag reasons after review in practice sessions to see patterns here.
        </div>
      ) : (
        <div className="space-y-3 pt-1">
          {items.map((item) => {
            const label = item.label || item.reason_label || item.reason
            const percentage = item.percentage ?? item.share_pct ?? 0
            return (
              <div key={item.reason} className="space-y-1">
                <div className="flex items-center justify-between text-xs">
                  <span className="text-text font-medium capitalize">{label}</span>
                  <span className="text-text-subtle">
                    {item.count} ({percentage}%)
                  </span>
                </div>
                <ProgressBar value={percentage} label={`${label} percentage`} size="sm" />
              </div>
            )
          })}
        </div>
      )}
    </Card>
  )
}
