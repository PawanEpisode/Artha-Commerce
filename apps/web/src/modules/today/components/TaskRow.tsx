import { Badge, Button, Checkbox, Clock, Ellipsis, Flag } from '@artha/design-system'
import { useState } from 'react'

import { isLocalTask } from '../lib/optimistic'
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
  /** The "Still relevant?" answers for a stuck own task (FR-F13-29). */
  onKeep?: (task: Task) => void
  onStuckSnooze?: (task: Task) => void
  onStuckDelete?: (task: Task) => void
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
  onKeep,
  onStuckSnooze,
  onStuckDelete,
}: TaskRowProps) {
  const [expanded, setExpanded] = useState(false)
  // A task made offline exists only on this device until the queue replays it: it cannot be ticked or edited yet.
  const waiting = isLocalTask(task)
  const inert = readOnly || waiting
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
      className={`flex items-start gap-2.5 px-3 py-2 ${
        highlighted ? 'bg-primary/10 ring-2 ring-primary/40 ring-inset' : ''
      } ${quiet ? 'opacity-75' : ''}`}
    >
      <Checkbox
        id={`task-${task.id}-check`}
        checked={done}
        disabled={inert || busy || !(open || (done && undoable))}
        aria-label={done ? `${task.title}, done` : `Mark done: ${task.title}`}
        onCheckedChange={(next) => (next === true ? onTick?.(task) : onUntick?.(task))}
        className="mt-0.5"
      />
      <div className="min-w-0 flex-1 space-y-0.5">
        <p
          className={`font-medium break-words ${expanded || !long ? '' : 'line-clamp-2'} ${
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
        {task.reason ? <p className="text-xs text-muted-foreground">{task.reason}</p> : null}
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
          {task.is_bonus ? <Badge variant="outline">Bonus</Badge> : null}
          {note ? <Badge variant="outline">{note}</Badge> : null}
          {waiting ? <Badge variant="outline">Waiting to sync</Badge> : null}
          {done ? <span className="sr-only">Done</span> : null}
        </p>
        {task.stuck && !inert ? (
          <div
            role="group"
            aria-label={`Still relevant? ${task.title}`}
            className="mt-1.5 space-y-1.5 rounded-md border border-border bg-secondary p-2.5"
          >
            <p className="text-[13px] font-medium">Still relevant?</p>
            <p className="text-xs text-muted-foreground">This has been on your list for a few days.</p>
            <div className="flex flex-wrap gap-2">
              <Button size="sm" variant="outline" disabled={busy} onClick={() => onKeep?.(task)}>
                Keep
              </Button>
              <Button size="sm" variant="outline" disabled={busy} onClick={() => onStuckSnooze?.(task)}>
                Snooze
              </Button>
              <Button size="sm" variant="outline" disabled={busy} onClick={() => onStuckDelete?.(task)}>
                Delete
              </Button>
            </div>
          </div>
        ) : null}
      </div>
      {!inert ? (
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
            size="icon-sm"
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
