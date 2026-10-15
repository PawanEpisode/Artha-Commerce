import { Badge, CircleCheck, Clock, Flag, Square } from '@artha/design-system'
import { Link } from '@tanstack/react-router'

import { progressText } from '../lib/plan'
import { formatMinutes } from '../lib/time'
import type { Task } from '../lib/types'

const STATE_NOTE: Partial<Record<Task['state'], string>> = { skipped: 'Skipped', snoozed: 'Snoozed' }

/** One task. W4 shows it; ticking, the menu and swap arrive with the actions (W5), so the marker is a status, not a button. */
export function TaskRow({ task, highlighted = false }: { task: Task; highlighted?: boolean }) {
  const done = task.state === 'done'
  const quiet = task.state === 'skipped' || task.state === 'snoozed'
  const progress = progressText(task)
  const note = STATE_NOTE[task.state]
  const title = task.link ? (
    <Link
      to={task.link.path as never}
      search={task.link.search as never}
      className="rounded font-semibold underline-offset-4 hover:underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
    >
      {task.title}
    </Link>
  ) : (
    <span className="font-semibold">{task.title}</span>
  )
  return (
    <li
      id={`task-${task.id}`}
      data-state={task.state}
      data-highlighted={highlighted || undefined}
      className={`flex items-start gap-3 rounded-xl border bg-card p-3 sm:p-4 ${
        highlighted ? 'border-primary ring-2 ring-primary/30' : 'border-border'
      } ${quiet ? 'opacity-75' : ''}`}
    >
      {done ? (
        <CircleCheck aria-hidden className="mt-0.5 size-5 shrink-0 text-success" />
      ) : (
        <Square aria-hidden className="mt-0.5 size-5 shrink-0 text-muted-foreground" />
      )}
      <div className="min-w-0 flex-1 space-y-1">
        <p className={`break-words ${done || quiet ? 'text-muted-foreground' : ''} ${done ? 'line-through' : ''}`}>
          {title}
        </p>
        {task.reason ? <p className="text-sm text-muted-foreground">{task.reason}</p> : null}
        <p className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
          <span className="inline-flex items-center gap-1">
            <Clock aria-hidden className="size-3.5" />
            {formatMinutes(task.est_minutes)}
          </span>
          {progress ? <span>{progress}</span> : null}
          {task.is_must_do ? (
            <Badge variant="highlight">
              <Flag aria-hidden /> Must do
            </Badge>
          ) : null}
          {note ? <Badge variant="outline">{note}</Badge> : null}
          {done ? <span className="sr-only">Done</span> : null}
        </p>
      </div>
    </li>
  )
}
