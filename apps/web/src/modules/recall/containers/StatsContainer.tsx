import { EmptyState, Layers, PageHeader, SegmentedControl, Skeleton } from '@artha/design-system'
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
      <PageHeader
        title="Revision stats"
        description="How much you reviewed and how much you remember."
        actions={
          <SegmentedControl
            label="Time range"
            value={search.range}
            onValueChange={(range) => void navigate({ to: '/app/recall/stats', search: { range } })}
            options={RANGES}
          />
        }
      />
      {summary.isPending ? (
        <div aria-busy="true" className="space-y-3">
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            {Array.from({ length: 4 }, (_, i) => (
              <Skeleton key={i} className="h-20 w-full" />
            ))}
          </div>
          <Skeleton className="h-56 w-full" />
        </div>
      ) : summary.isError || !summary.data ? (
        <LoadError what="your stats" onRetry={() => void summary.refetch()} />
      ) : summary.data.reviews === 0 && !forecast.data?.days.some((d) => d.due > 0) ? (
        <EmptyState
          className="rounded-lg py-6"
          icon={<Layers aria-hidden />}
          title="No reviews yet"
          description="Finish a review session and your numbers appear here."
        />
      ) : (
        <>
          <SummaryTiles s={summary.data} />
          <div className="grid gap-3 xl:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
            <div className="grid min-w-0 content-start gap-3 md:grid-cols-2">
              <ReviewsChart s={summary.data} />
              {retention.data ? <RetentionChart r={retention.data} /> : null}
              {forecast.data ? <ForecastChart f={forecast.data} className="md:col-span-2" /> : null}
            </div>
            {chapters.data ? (
              <section aria-labelledby="strength-heading" className="min-w-0 space-y-2">
                <h2 id="strength-heading" className="text-sm font-semibold">
                  Chapter by chapter
                </h2>
                <ChapterStrengthList data={chapters.data} />
              </section>
            ) : null}
          </div>
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
