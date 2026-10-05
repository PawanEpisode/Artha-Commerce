import { Alert, Button, EmptyState, Skeleton, TextField, Timer } from '@artha/design-system'
import { useNavigate } from '@tanstack/react-router'

import { SessionsPanel, useTrackerSettings } from '~/modules/tracker'

import { useHistory } from '../hooks/useFocusQueries'
import { isFeatureDisabled } from '../lib/api'
import { FocusShell } from './FocusShell'

export interface HistorySearch {
  date?: string
}

function Body({ date, tz, defaultActivity }: { date?: string; tz: string; defaultActivity: 'other' | never } & object) {
  const navigate = useNavigate()
  const q = useHistory(date ? { from: date, to: date } : {})
  const rows = q.data?.pages.flatMap((p) => p.results) ?? []
  const days = [...new Set(rows.map((r) => r.study_date))]
  return (
    <>
      <header className="space-y-1">
        <h1 className="text-3xl font-extrabold">Focus history</h1>
        <p className="text-muted-foreground">Every finished round, newest first. Edit, split or delete from here.</p>
      </header>
      <form className="flex flex-wrap items-end gap-3" onSubmit={(e) => e.preventDefault()} aria-label="Filter by day">
        <TextField
          label="Day"
          type="date"
          value={date ?? ''}
          onChange={(e) => void navigate({ to: '/app/focus/history', search: { date: e.target.value || undefined } })}
        />
        {date ? (
          <Button
            type="button"
            variant="outline"
            onClick={() => void navigate({ to: '/app/focus/history', search: {} })}
          >
            Show all days
          </Button>
        ) : null}
      </form>
      {q.isPending ? (
        <Skeleton className="h-40 w-full" />
      ) : q.isError ? (
        <Alert variant="error">
          <span role="alert">We could not load your history.</span>
        </Alert>
      ) : rows.length === 0 ? (
        <EmptyState
          icon={<Timer aria-hidden />}
          title={date ? 'No rounds on this day' : 'No rounds yet'}
          description="Finished focus rounds show up here."
        />
      ) : (
        days.map((day) => (
          <section key={day} aria-labelledby={`day-${day}`} className="space-y-2">
            <h2 id={`day-${day}`} className="text-lg font-bold">
              {new Date(`${day}T00:00:00`).toLocaleDateString(undefined, {
                weekday: 'long',
                day: 'numeric',
                month: 'long',
              })}
            </h2>
            <SessionsPanel
              sessions={rows.filter((r) => r.study_date === day)}
              tz={tz}
              defaultActivity={defaultActivity}
            />
          </section>
        ))
      )}
      {q.hasNextPage ? (
        <Button variant="outline" onClick={() => void q.fetchNextPage()} disabled={q.isFetchingNextPage}>
          Load older rounds
        </Button>
      ) : null}
    </>
  )
}

export function HistoryContainer({ search }: { search: HistorySearch }) {
  const settings = useTrackerSettings()
  return (
    <FocusShell
      state={
        settings.isPending ? 'loading' : settings.isError && !isFeatureDisabled(settings.error) ? 'error' : 'ready'
      }
      disabled={false}
      onRetry={() => void settings.refetch()}
    >
      {settings.data ? (
        <Body
          date={search.date}
          tz={settings.data.tz}
          defaultActivity={settings.data.default_activity_type as 'other'}
        />
      ) : null}
    </FocusShell>
  )
}
