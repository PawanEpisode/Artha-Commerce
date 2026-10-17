import { Skeleton, StatTile } from '@artha/design-system'

import type { OverviewData } from '../lib/types'

interface OverviewCardsProps {
  data?: OverviewData
  isLoading?: boolean
}

export function OverviewCards({ data, isLoading }: OverviewCardsProps) {
  if (isLoading || !data) {
    return (
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        <Skeleton className="h-24 rounded-lg" />
        <Skeleton className="h-24 rounded-lg" />
        <Skeleton className="h-24 rounded-lg" />
        <Skeleton className="h-24 rounded-lg" />
      </div>
    )
  }

  const totalAnswered = data.total_answered ?? 0
  const totalCorrect = data.total_correct ?? 0
  const accPct = data.overall_accuracy_pct ?? Math.round((data.overall_accuracy ?? 0) * 100)
  const studyHours =
    data.study_hours_formatted ??
    (data.study_seconds
      ? `${Math.floor(data.study_seconds / 3600)}h ${Math.floor((data.study_seconds % 3600) / 60)}m`
      : '0m')
  const daysActive = data.days_active ?? (data as unknown as { distinct_study_days?: number }).distinct_study_days ?? 0

  return (
    <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
      <StatTile
        label="Questions Answered"
        value={totalAnswered.toLocaleString()}
        hint={`${totalCorrect} answered correctly`}
      />
      <StatTile
        label="Overall Accuracy"
        value={`${accPct}%`}
        hint={accPct >= 70 ? 'On target for exam benchmark' : 'Target is 70%+'}
      />
      <StatTile label="Study Time" value={studyHours} hint="Practice and stopwatch time" />
      <StatTile label="Active Days" value={daysActive.toString()} hint="Days with recorded practice" />
    </div>
  )
}
