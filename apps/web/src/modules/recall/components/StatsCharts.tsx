import { BarChart, ProgressBar, StatTile } from '@artha/design-system'

import { chapterTitle, forecastColumns, retentionColumns, reviewColumns, strengthOf } from '../lib/charts'
import { minutesLabel, percent, plural } from '../lib/format'
import type { StatsChapters, StatsForecast, StatsRetention, StatsSummary } from '../lib/schemas'

export function SummaryTiles({ s }: { s: StatsSummary }) {
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
      <StatTile label="Reviews" value={s.reviews} hint={`${s.new_cards} new`} />
      <StatTile label="Time" value={minutesLabel(s.minutes * 60)} />
      <StatTile label="Streak" value={plural(s.streak, 'day')} hint={`Longest ${plural(s.longest_streak, 'day')}`} />
      <StatTile label="Remembered" value={percent(s.true_retention)} hint="Of cards you had learned" />
    </div>
  )
}

export function ReviewsChart({ s }: { s: StatsSummary }) {
  return (
    <BarChart
      title="Reviews per day"
      series={[{ key: 'reviews', name: 'Reviews' }]}
      columns={reviewColumns(s)}
      format={(n) => `${n} ${n === 1 ? 'review' : 'reviews'}`}
      labelEvery={s.series.length > 14 ? 5 : 1}
    />
  )
}

export function RetentionChart({ r }: { r: StatsRetention }) {
  return (
    <div className="space-y-2">
      <BarChart
        title="Remembered when you saw the card again"
        series={[{ key: 'retention', name: 'Remembered' }]}
        columns={retentionColumns(r)}
        format={(n) => `${n}%`}
        labelEvery={r.series.length > 14 ? 5 : 1}
      />
      <p className="text-sm text-muted-foreground">
        Your target is {percent(r.target)}. Overall: {percent(r.overall)}.
      </p>
    </div>
  )
}

export function ForecastChart({ f }: { f: StatsForecast }) {
  return (
    <div className="space-y-2">
      <BarChart
        title="Cards due in the next 30 days"
        series={[{ key: 'due', name: 'Due' }]}
        columns={forecastColumns(f)}
        format={(n) => `${n} due`}
        labelEvery={5}
      />
      {f.overdue > 0 ? (
        <p className="text-sm text-muted-foreground">{plural(f.overdue, 'card')} already past due.</p>
      ) : null}
    </div>
  )
}

export function ChapterStrengthList({ data }: { data: StatsChapters }) {
  if (data.chapters.length === 0) return <p className="text-sm text-muted-foreground">No chapters with cards yet.</p>
  return (
    <ul className="space-y-3">
      {data.chapters.map((c, i) => {
        const s = strengthOf(c.strength)
        return (
          <li key={c.chapter?.id ?? `none-${i}`} className="space-y-1.5">
            <div className="flex items-baseline justify-between gap-3 text-sm">
              <span className="font-medium">{chapterTitle(c)}</span>
              <span className="text-muted-foreground">
                {s.label}
                {c.strength !== null ? ` · ${s.value}%` : ''} · {plural(c.cards, 'card')}
                {c.due > 0 ? ` · ${c.due} due` : ''}
              </span>
            </div>
            <ProgressBar
              value={s.value}
              label={`${chapterTitle(c)} strength`}
              size="sm"
              aria-valuetext={`${s.label}, ${s.value}%`}
            />
          </li>
        )
      })}
    </ul>
  )
}
