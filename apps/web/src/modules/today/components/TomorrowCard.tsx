import { ArrowRight, CalendarClock } from '@artha/design-system'
import { Link } from '@tanstack/react-router'

import { formatMinutes } from '../lib/time'
import type { Preview } from '../lib/types'

/** Tomorrow's likely tasks, labelled "may change". Never stored: it only reads the preview. */
export function TomorrowCard({ preview }: { preview: Preview }) {
  const own = preview.own_tasks.length
  const count = preview.count + own
  if (count === 0) return null
  const minutes = preview.minutes + preview.own_tasks.reduce((s, t) => s + t.est_minutes, 0)
  return (
    <section aria-labelledby="tomorrow-heading" className="space-y-2 rounded-2xl border border-border bg-card p-4">
      <h2 id="tomorrow-heading" className="flex items-center gap-2 font-display text-lg font-bold">
        <CalendarClock aria-hidden className="size-5 text-primary" /> Tomorrow
      </h2>
      <p className="text-sm text-muted-foreground">
        {count === 1 ? '1 task' : `${count} tasks`}, about {formatMinutes(minutes)}. This may change.
      </p>
      <ul className="space-y-1 text-sm">
        {preview.tasks.map((t) => (
          <li key={`${t.kind}-${t.title}`} className="break-words">
            {t.title}
          </li>
        ))}
        {preview.own_tasks.map((t) => (
          <li key={t.id} className="break-words">
            {t.title}
          </li>
        ))}
      </ul>
      <Link
        to={'/app/today/$date' as never}
        params={{ date: preview.date } as never}
        className="inline-flex min-h-11 items-center gap-1 text-sm font-semibold underline-offset-4 hover:underline"
      >
        See tomorrow <ArrowRight aria-hidden className="size-4" />
      </Link>
    </section>
  )
}
