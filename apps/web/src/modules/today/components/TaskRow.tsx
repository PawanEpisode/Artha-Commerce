import { Badge, Button, Checkbox, Clock, Ellipsis, Flag } from '@artha/design-system'
import { useState } from 'react'

import { progressText } from '../lib/plan'
import { formatMinutes } from '../lib/time'
import type { Task } from '../lib/types'

const STATE_NOTE: Partial<Record<Task['state'], string>> = { skipped: 'Skipped', snoozed: 'Snoozed' }
const LONG_TITLE = 80

export interface TaskRowProps {
  task: Task
  highlighted?: boolean
  /** A recap or a preview: no tick, no menu. */
  readOnly?: boolean
  /** A request for this task is in flight. */
  busy?: boolean
  /** The tick was the student's own and is still inside the 60 second undo window. */
  undoable?: boolean
  onTick?: (task: Task) => void
  onUntick?: (task: Task) => void
  onStart?: (task: Task) => void
  onMenu?: (task: Task) => void
}

/** One task: a 44 px tick, the title (two lines, expandable), reason, minutes, progress, Start and a menu. Every action is a button. */
export function TaskRow({
  task,
  highlighted = false,
  readOnly = false,
  busy = false,
  undoable = false,
  onTick,
  onUntick,
  onStart,
  onMenu,
}: TaskRowProps) {
  const [expanded, setExpanded] = useState(false)
  const done = task.state === 'done'
  const open = task.state === 'suggested' || task.state === 'accepted'
  const quiet = task.state === 'skipped' || task.state === 'snoozed'
  const progress = progressText(task)
  const note = STATE_NOTE[task.state]
  const long = task.title.length > LONG_TITLE
  return (
    <li
      id={`task-${task.id}`}
      data-state={task.state}
      data-highlighted={highlighted || undefined}
      className={`flex items-start gap-3 rounded-xl border bg-card p-3 sm:p-4 ${
        highlighted ? 'border-primary ring-2 ring-primary/30' : 'border-border'
      } ${quiet ? 'opacity-75' : ''}`}
    >
      <Checkbox
        id={`task-${task.id}-check`}
        checked={done}
        disabled={readOnly || busy || !(open || (done && undoable))}
        aria-label={done ? `${task.title}, done` : `Mark done: ${task.title}`}
        onCheckedChange={(next) => (next === true ? onTick?.(task) : onUntick?.(task))}
        className="mt-0.5"
      />
      <div className="min-w-0 flex-1 space-y-1">
        <p
          className={`font-semibold break-words ${expanded || !long ? '' : 'line-clamp-2'} ${
            done || quiet ? 'text-muted-foreground' : ''
          } ${done ? 'line-through' : ''}`}
        >
          {task.title}
        </p>
        {long ? (
          <button
            type="button"
            aria-expanded={expanded}
            onClick={() => setExpanded((v) => !v)}
            className="text-xs font-medium underline underline-offset-4"
          >
            {expanded ? 'Show less' : 'Expand'}
          </button>
        ) : null}
        {task.reason ? <p className="text-sm text-muted-foreground">{task.reason}</p> : null}
        <p className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
          <span className="inline-flex items-center gap-1">
            <Clock aria-hidden className="size-3.5" />
            {formatMinutes(task.est_minutes)}
          </span>
          {progress ? <span>{progress}</span> : null}
          {task.state === 'accepted' ? <Badge variant="accent">In progress</Badge> : null}
          {task.is_must_do ? (
            <Badge variant="highlight">
              <Flag aria-hidden /> Must do
            </Badge>
          ) : null}
          {note ? <Badge variant="outline">{note}</Badge> : null}
          {done ? <span className="sr-only">Done</span> : null}
        </p>
      </div>
      {!readOnly ? (
        <div className="flex shrink-0 items-center gap-1">
          {open && task.link ? (
            <Button
              variant="outline"
              size="sm"
              disabled={busy}
              onClick={() => onStart?.(task)}
              aria-label={`${task.state === 'accepted' ? 'Continue' : 'Start'}: ${task.title}`}
            >
              {task.state === 'accepted' ? 'Continue' : 'Start'}
            </Button>
          ) : null}
          <Button
            variant="ghost"
            size="icon"
            id={`task-${task.id}-menu`}
            aria-label={`More actions for ${task.title}`}
            aria-haspopup="dialog"
            onClick={() => onMenu?.(task)}
          >
            <Ellipsis aria-hidden />
          </Button>
        </div>
      ) : null}
    </li>
  )
}
