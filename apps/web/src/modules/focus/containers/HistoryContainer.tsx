import { Alert, Button, EmptyState, PageHeader, Skeleton, TableToolbar, TextField, Timer } from '@artha/design-system'
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
  return (
    <>
      <PageHeader
        title="Focus history"
        description="Every finished round, newest first. Edit, split or delete from here."
      />
      <form onSubmit={(e) => e.preventDefault()} aria-label="Filter by day">
        <TableToolbar className="items-end">
          <TextField
            label="Day"
            type="date"
            className="w-40"
            value={date ?? ''}
            onChange={(e) => void navigate({ to: '/app/focus/history', search: { date: e.target.value || undefined } })}
          />
          {date ? (
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => void navigate({ to: '/app/focus/history', search: {} })}
            >
              Show all days
            </Button>
          ) : null}
        </TableToolbar>
      </form>
      {q.isPending ? (
        <Skeleton className="h-28 w-full" />
      ) : q.isError ? (
        <Alert variant="error">
          <span role="alert">We could not load your history.</span>
        </Alert>
      ) : rows.length === 0 ? (
        <EmptyState
          className="rounded-lg py-6"
          icon={<Timer aria-hidden />}
          title={date ? 'No rounds on this day' : 'No rounds yet'}
          description="Finished focus rounds show up here."
        />
      ) : (
        <SessionsPanel sessions={rows} tz={tz} defaultActivity={defaultActivity} groupByDay label="Focus history" />
      )}
      {q.hasNextPage ? (
        <Button variant="outline" size="sm" onClick={() => void q.fetchNextPage()} disabled={q.isFetchingNextPage}>
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
