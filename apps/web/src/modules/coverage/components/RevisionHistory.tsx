import type { CoverageEventRow } from '../lib/types'

const LABEL: Record<string, string> = {
  practice_done: 'Practice set',
  mock_done: 'Mock test',
  revision_done: 'Revision',
}

const formatDate = (iso: string | null) =>
  iso ? new Date(iso).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' }) : ''

/** What the student has logged on this chapter, newest first. */
export function ActivityLog({ events }: { events: CoverageEventRow[] }) {
  const logged = events.filter((e) => e.type in LABEL)
  if (logged.length === 0) return <p className="text-sm text-muted-foreground">Nothing logged yet.</p>
  return (
    <ol className="divide-y rounded-xl border bg-card">
      {logged.map((e) => (
        <li key={e.id} className="flex items-center justify-between gap-3 px-4 py-3 text-sm">
          <span className="font-medium">
            {LABEL[e.type]}
            {e.value !== null ? <span className="text-muted-foreground"> · {e.value}%</span> : null}
          </span>
          <time dateTime={e.occurred_at ?? undefined} className="text-muted-foreground">
            {formatDate(e.occurred_at)}
          </time>
        </li>
      ))}
    </ol>
  )
}
