import {
  BarChart,
  DataTable,
  ProgressBar,
  StatTile,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@artha/design-system'
import type { ReactNode } from 'react'

import { chapterTitle, forecastColumns, retentionColumns, reviewColumns, strengthOf } from '../lib/charts'
import { minutesLabel, percent, plural } from '../lib/format'
import type { StatsChapters, StatsForecast, StatsRetention, StatsSummary } from '../lib/schemas'

/** A compact chart card: the chart plus an optional muted note under it. */
function ChartCard({ children, note, className }: { children: ReactNode; note?: ReactNode; className?: string }) {
  return (
    <div className={`min-w-0 space-y-2 rounded-lg border border-border bg-card p-4 ${className ?? ''}`}>
      {children}
      {note ? <p className="text-[13px] text-muted-foreground">{note}</p> : null}
    </div>
  )
}

export function SummaryTiles({ s }: { s: StatsSummary }) {
  return (
    <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
      <StatTile label="Reviews" value={s.reviews} hint={`${s.new_cards} new`} />
      <StatTile label="Time" value={minutesLabel(s.minutes * 60)} />
      <StatTile label="Streak" value={plural(s.streak, 'day')} hint={`Longest ${plural(s.longest_streak, 'day')}`} />
      <StatTile label="Remembered" value={percent(s.true_retention)} hint="Of cards you had learned" />
    </div>
  )
}

export function ReviewsChart({ s }: { s: StatsSummary }) {
  return (
    <ChartCard>
      <BarChart
        title="Reviews per day"
        series={[{ key: 'reviews', name: 'Reviews' }]}
        columns={reviewColumns(s)}
        format={(n) => `${n} ${n === 1 ? 'review' : 'reviews'}`}
        labelEvery={s.series.length > 14 ? 5 : 1}
        height={120}
      />
    </ChartCard>
  )
}

export function RetentionChart({ r }: { r: StatsRetention }) {
  return (
    <ChartCard note={`Your target is ${percent(r.target)}. Overall: ${percent(r.overall)}.`}>
      <BarChart
        title="Remembered when you saw the card again"
        series={[{ key: 'retention', name: 'Remembered' }]}
        columns={retentionColumns(r)}
        format={(n) => `${n}%`}
        labelEvery={r.series.length > 14 ? 5 : 1}
        height={120}
      />
    </ChartCard>
  )
}

export function ForecastChart({ f, className }: { f: StatsForecast; className?: string }) {
  return (
    <ChartCard
      className={className}
      note={f.overdue > 0 ? `${plural(f.overdue, 'card')} already past due.` : undefined}
    >
      <BarChart
        title="Cards due in the next 30 days"
        series={[{ key: 'due', name: 'Due' }]}
        columns={forecastColumns(f)}
        format={(n) => `${n} due`}
        labelEvery={5}
        height={120}
      />
    </ChartCard>
  )
}

/** The breakdown next to the charts: one row per chapter with its strength in words, a thin bar and its counts. */
export function ChapterStrengthList({ data }: { data: StatsChapters }) {
  if (data.chapters.length === 0)
    return <p className="text-[13px] text-muted-foreground">No chapters with cards yet.</p>
  return (
    <DataTable aria-labelledby="strength-heading">
      <TableHeader>
        <TableRow>
          <TableHead>Chapter</TableHead>
          <TableHead>Strength</TableHead>
          <TableHead className="text-right">Cards</TableHead>
          <TableHead className="text-right">Due</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {data.chapters.map((c, i) => {
          const s = strengthOf(c.strength)
          return (
            <TableRow key={c.chapter?.id ?? `none-${i}`}>
              <TableCell className="max-w-0 min-w-32 truncate font-medium">{chapterTitle(c)}</TableCell>
              <TableCell className="min-w-32">
                <div className="space-y-1 py-1">
                  <p className="text-xs text-muted-foreground">
                    {s.label}
                    {c.strength !== null ? ` · ${s.value}%` : ''}
                  </p>
                  <ProgressBar
                    value={s.value}
                    label={`${chapterTitle(c)} strength`}
                    size="sm"
                    aria-valuetext={`${s.label}, ${s.value}%`}
                  />
                </div>
              </TableCell>
              <TableCell className="text-right text-muted-foreground tabular-nums">{c.cards}</TableCell>
              <TableCell className="text-right text-muted-foreground tabular-nums">{c.due > 0 ? c.due : ''}</TableCell>
            </TableRow>
          )
        })}
      </TableBody>
    </DataTable>
  )
}
