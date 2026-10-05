import { Card, CardContent } from '@artha/design-system'

import { formatDuration } from '../lib/duration'
import { dayLabel, shortDay } from '../lib/format'
import type { WeeklySummary } from '../lib/types'

/** Last week in a few sentences, with one suggestion. */
export function WeeklySummaryCard({ data }: { data: WeeklySummary }) {
  const s = data.suggestion
  return (
    <Card>
      <CardContent className="space-y-3 p-6">
        <h2 className="text-lg font-bold">
          Your week, {shortDay(data.week_start)} to {shortDay(data.week_end)}
        </h2>
        {data.total_seconds === 0 ? (
          <p className="text-muted-foreground">No study time was logged that week.</p>
        ) : (
          <ul className="list-disc space-y-1 pl-5 text-sm">
            <li>
              You studied {formatDuration(data.total_seconds)} over {data.days_tracked}{' '}
              {data.days_tracked === 1 ? 'day' : 'days'}.
            </li>
            {data.best_day ? (
              <li>
                Your best day was {dayLabel(data.best_day.date)}, with {formatDuration(data.best_day.seconds)}.
              </li>
            ) : null}
            {data.top_subject ? (
              <li>
                Most time went to {data.top_subject.name} ({formatDuration(data.top_subject.seconds)}).
              </li>
            ) : null}
            {data.goal ? (
              <li>
                {data.goal.met
                  ? `You met your weekly goal of ${formatDuration(data.goal.target_minutes * 60)}.`
                  : `You were ${formatDuration(data.goal.target_minutes * 60 - data.goal.done_seconds)} short of your weekly goal.`}
              </li>
            ) : null}
          </ul>
        )}
        <p className="text-sm font-medium">
          {s.kind === 'subject_shortfall'
            ? `Next week, try ${formatDuration(s.remaining_seconds)} more on ${s.subject_name}.`
            : 'Keep going. Your routine is working.'}
        </p>
      </CardContent>
    </Card>
  )
}
