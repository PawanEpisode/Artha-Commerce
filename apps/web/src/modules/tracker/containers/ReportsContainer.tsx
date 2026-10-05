import { Alert, BarChart, Heatmap, SegmentedControl, Select, Skeleton } from '@artha/design-system'
import { useNavigate } from '@tanstack/react-router'
import { type ReactNode, useEffect, useMemo, useRef } from 'react'

import { track } from '~/modules/observability'

import { BreakdownList } from '../components/BreakdownList'
import { ReportToolbar } from '../components/ReportToolbar'
import { SummaryTiles } from '../components/SummaryTiles'
import { TimeVsCoverageTable } from '../components/TimeVsCoverageTable'
import { useSubjectOptions } from '../hooks/useTagOptions'
import {
  useBreakdown,
  useHeatmap,
  useHours,
  useSeries,
  useSummary,
  useTimeVsCoverage,
  useToday,
} from '../hooks/useTrackerQueries'
import { downloadCsv } from '../lib/api'
import { toChartModel } from '../lib/chartData'
import { addDays, formatDuration } from '../lib/duration'
import { dayLabel, WEEKDAYS_MON, WEEKDAYS_SUN } from '../lib/format'
import { heatCells } from '../lib/heatmap'
import { defaultGroup, presetRange, type RangePreset, rangeProblem } from '../lib/range'
import type { SplitBy } from '../lib/types'
import { TrackerShell } from './TrackerShell'

export interface ReportsSearch {
  range: RangePreset
  from?: string
  to?: string
  by: 'total' | 'subject' | 'activity'
  subject?: string
}

function Block({
  query,
  children,
  label,
}: {
  query: { isPending: boolean; isError: boolean }
  children: ReactNode
  label: string
}) {
  if (query.isPending) return <Skeleton className="h-40 w-full" aria-label={`Loading ${label}`} />
  if (query.isError)
    return (
      <Alert variant="error">
        <span role="alert">We could not load {label}.</span>
      </Alert>
    )
  return <>{children}</>
}

const Card = ({ children, title }: { children: ReactNode; title: string }) => (
  <section aria-label={title} className="space-y-3 rounded-2xl border border-border bg-card p-5 shadow-soft">
    {children}
  </section>
)

function Reports({ search, tz, weekStart }: { search: ReportsSearch; tz: string; weekStart: 0 | 1 }) {
  void tz
  const navigate = useNavigate()
  const today = useToday()
  const subjects = useSubjectOptions()
  const range = useMemo(
    () =>
      presetRange(
        search.range,
        today,
        weekStart,
        search.from && search.to ? { from: search.from, to: search.to } : undefined,
      ),
    [search.range, search.from, search.to, today, weekStart],
  )
  const problem = rangeProblem(range)
  const params = { from: range.from, to: range.to }
  const group = defaultGroup(range)
  const by: SplitBy = search.by

  const setSearch = (patch: Partial<ReportsSearch>) =>
    void navigate({ to: '/app/tracker/reports', search: { ...search, ...patch }, replace: true })

  const summary = useSummary({ ...params, compare: true })
  const series = useSeries({ ...params, group, by })
  const subjectSplit = useBreakdown({ ...params, by: 'subject' })
  const activitySplit = useBreakdown({ ...params, by: 'activity' })
  // The heat map is a year view: it follows a short range with the last 12 months so it is never nearly empty.
  const heatRange = { from: addDays(range.to, -364), to: range.to }
  const heat = useHeatmap(heatRange)
  const hours = useHours(params)
  const chosenSubject = search.subject ?? subjects[0]?.id
  const tvc = useTimeVsCoverage({ ...params, subject_id: chosenSubject })

  const viewed = useRef(false)
  useEffect(() => {
    if (summary.data && !viewed.current) {
      viewed.current = true
      track('report_viewed', { range: search.range, split: by })
    }
  }, [summary.data, search.range, by])

  const chart = series.data ? toChartModel(series.data, group, by) : null
  const weekdays = weekStart === 1 ? WEEKDAYS_MON : WEEKDAYS_SUN
  const fmt = formatDuration

  return (
    <>
      <header className="space-y-1">
        <h1 className="text-3xl font-extrabold">Reports</h1>
        <p className="text-muted-foreground">
          {dayLabel(range.from)} to {dayLabel(range.to)}
        </p>
      </header>

      <ReportToolbar
        preset={search.range}
        range={range}
        problem={problem}
        onPreset={(r) =>
          setSearch({
            range: r,
            ...(r === 'custom' ? { from: range.from, to: range.to } : { from: undefined, to: undefined }),
          })
        }
        onCustom={(r) => setSearch({ range: 'custom', from: r.from, to: r.to })}
        exporting={false}
        onExport={() => {
          track('report_exported', { range: search.range })
          void downloadCsv('/tracking/reports/export.csv', { ...params, by: 'subject' }, 'study-report.csv')
        }}
      />

      {problem ? null : (
        <>
          <Block query={summary} label="the summary">
            {summary.data ? <SummaryTiles summary={summary.data} /> : null}
          </Block>

          <Card title="Study time">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <h2 className="text-lg font-bold">Study time</h2>
              <SegmentedControl<ReportsSearch['by']>
                label="Split the chart by"
                value={search.by}
                onValueChange={(v) => setSearch({ by: v })}
                options={[
                  { value: 'total', label: 'Total' },
                  { value: 'subject', label: 'Subject' },
                  { value: 'activity', label: 'Activity' },
                ]}
              />
            </div>
            <Block query={series} label="the chart">
              {chart ? (
                <BarChart
                  title={`Study time by ${group}`}
                  series={chart.series}
                  columns={chart.columns}
                  format={fmt}
                  labelEvery={Math.max(1, Math.ceil(chart.columns.length / 12))}
                />
              ) : null}
            </Block>
          </Card>

          <div className="grid gap-4 md:grid-cols-2">
            <Card title="By subject">
              <Block query={subjectSplit} label="the subject split">
                {subjectSplit.data ? <BreakdownList title="By subject" data={subjectSplit.data} /> : null}
              </Block>
            </Card>
            <Card title="By activity">
              <Block query={activitySplit} label="the activity split">
                {activitySplit.data ? <BreakdownList title="By activity" data={activitySplit.data} /> : null}
              </Block>
            </Card>
          </div>

          <Card title="Calendar">
            <Block query={heat} label="the calendar">
              {heat.data ? (
                <Heatmap
                  title="Study days over the last 12 months"
                  cells={heatCells(heat.data.days, heatRange.from, heatRange.to, weekStart)}
                  weekdayLabels={[...weekdays]}
                  legend={{ less: 'Less', more: 'More' }}
                  onSelect={(date) => void navigate({ to: '/app/tracker/day/$date', params: { date } })}
                />
              ) : null}
            </Block>
          </Card>

          <Card title="Time of day">
            <Block query={hours} label="the time of day chart">
              {hours.data ? (
                <>
                  <BarChart
                    title="Study time by hour of day"
                    series={[{ key: 'seconds', name: 'Study time' }]}
                    columns={hours.data.hours.map((s, h) => ({
                      label: `${String(h).padStart(2, '0')}:00`,
                      short: String(h),
                      values: { seconds: s },
                    }))}
                    format={fmt}
                    labelEvery={3}
                    height={120}
                  />
                  <p className="text-xs text-muted-foreground">Hours are approximate for sessions with pauses.</p>
                </>
              ) : null}
            </Block>
          </Card>

          <Card title="Time against coverage">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <h2 className="text-lg font-bold">Time against coverage</h2>
              {subjects.length > 0 ? (
                <Select
                  aria-label="Subject"
                  value={chosenSubject}
                  onChange={(e) => setSearch({ subject: e.target.value })}
                  className="w-56"
                >
                  {subjects.map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.name}
                    </option>
                  ))}
                </Select>
              ) : null}
            </div>
            {subjects.length === 0 ? (
              <p className="text-sm text-muted-foreground">Set up My Coverage to compare time with progress.</p>
            ) : (
              <Block query={tvc} label="the comparison">
                {tvc.data ? <TimeVsCoverageTable data={tvc.data} /> : null}
              </Block>
            )}
          </Card>
        </>
      )}
    </>
  )
}

export function ReportsContainer({ search }: { search: ReportsSearch }) {
  return <TrackerShell>{(tz, weekStart) => <Reports search={search} tz={tz} weekStart={weekStart} />}</TrackerShell>
}
