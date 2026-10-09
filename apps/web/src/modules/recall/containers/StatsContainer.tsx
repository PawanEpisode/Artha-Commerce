import { EmptyState, Layers, SegmentedControl, Skeleton } from '@artha/design-system'
import { useNavigate } from '@tanstack/react-router'

import { LoadError, RecallShell } from '../components/RecallShell'
import {
  ChapterStrengthList,
  ForecastChart,
  RetentionChart,
  ReviewsChart,
  SummaryTiles,
} from '../components/StatsCharts'
import { useStatsChapters, useStatsForecast, useStatsRetention, useStatsSummary } from '../hooks/useStats'
import type { StatsSearch } from '../lib/search'

const RANGES = [
  { value: '7d', label: '7 days' },
  { value: '30d', label: '30 days' },
  { value: '90d', label: '90 days' },
] as const

function Stats({ search }: { search: StatsSearch }) {
  const navigate = useNavigate()
  const summary = useStatsSummary(search.range)
  const retention = useStatsRetention(search.range)
  const forecast = useStatsForecast(30)
  const chapters = useStatsChapters()

  return (
    <>
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div className="space-y-1">
          <h1 className="text-3xl font-extrabold">Revision stats</h1>
          <p className="text-muted-foreground">How much you reviewed and how much you remember.</p>
        </div>
        <SegmentedControl
          label="Time range"
          value={search.range}
          onValueChange={(range) => void navigate({ to: '/app/recall/stats', search: { range } })}
          options={RANGES}
        />
      </header>
      {summary.isPending ? (
        <Skeleton className="h-64 w-full" aria-busy="true" />
      ) : summary.isError || !summary.data ? (
        <LoadError what="your stats" onRetry={() => void summary.refetch()} />
      ) : summary.data.reviews === 0 && !forecast.data?.days.some((d) => d.due > 0) ? (
        <EmptyState
          icon={<Layers aria-hidden />}
          title="No reviews yet"
          description="Finish a review session and your numbers appear here."
        />
      ) : (
        <>
          <SummaryTiles s={summary.data} />
          <ReviewsChart s={summary.data} />
          {retention.data ? <RetentionChart r={retention.data} /> : null}
          {forecast.data ? <ForecastChart f={forecast.data} /> : null}
          {chapters.data ? (
            <section aria-labelledby="strength-heading" className="space-y-3">
              <h2 id="strength-heading" className="font-display text-lg font-bold">
                Chapter by chapter
              </h2>
              <ChapterStrengthList data={chapters.data} />
            </section>
          ) : null}
        </>
      )}
    </>
  )
}

export function StatsContainer({ search }: { search: StatsSearch }) {
  return (
    <RecallShell>
      <Stats search={search} />
    </RecallShell>
  )
}
