import {
  addIsoDays,
  AlarmClock,
  Button,
  DatePicker,
  Info,
  Label,
  Pencil,
  RadioCardItem,
  RadioGroup,
  Sheet,
  SheetContent,
  SheetDescription,
  SheetFooter,
  SheetHeader,
  SheetTitle,
  Shuffle,
  SkipForward,
  Switch,
  TextField,
  Trash2,
  Undo2,
} from '@artha/design-system'
import { Link } from '@tanstack/react-router'
import { type ReactNode, useEffect, useState } from 'react'

import { useMediaQuery } from '../hooks/useMediaQuery'
import type { TaskActions } from '../hooks/useTaskActions'
import { errorCode, errorMessage } from '../lib/api'
import { OWN_EST_MAX, OWN_EST_MIN, OWN_TASK_MAX_DAYS_AHEAD, TITLE_MAX } from '../lib/limits'
import type { SkipReason, SnoozeUntil, Task } from '../lib/types'

export type SheetMode = 'menu' | 'why' | 'skip' | 'snooze' | 'tick' | 'edit'

const SKIP_REASONS: Array<{ value: SkipReason | 'none'; label: string }> = [
  { value: 'none', label: 'No reason' },
  { value: 'not_in_attempt', label: 'Not in my attempt' },
  { value: 'already_know', label: 'I already know it' },
  { value: 'no_time', label: 'No time today' },
  { value: 'other', label: 'Something else' },
]

const SNOOZE_CHOICES: Array<{ value: SnoozeUntil; label: string }> = [
  { value: 'tomorrow', label: 'Tomorrow' },
  { value: 'in_3_days', label: 'In 3 days' },
  { value: 'next_week', label: 'Next week' },
]

function MenuButton({ icon, children, onClick }: { icon: ReactNode; children: ReactNode; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="flex min-h-11 w-full items-center gap-3 rounded-xl px-3 py-2 text-left text-sm font-medium outline-none hover:bg-muted focus-visible:ring-[3px] focus-visible:ring-ring/40 [&_svg]:size-4 [&_svg]:text-muted-foreground"
    >
      {icon}
      {children}
    </button>
  )
}

const label = (value: string) => value.replace(/_/g, ' ').replace(/^./, (c) => c.toUpperCase())

function whyLines(task: Task): string[] {
  const lines: string[] = []
  for (const m of task.why.modifiers ?? []) {
    if (typeof m === 'string') lines.push(label(m))
    else if (m && typeof m === 'object') {
      const text = (m as { label?: unknown; code?: unknown }).label ?? (m as { code?: unknown }).code
      if (typeof text === 'string') lines.push(label(text))
    }
  }
  for (const [key, value] of Object.entries(task.why.signals ?? {})) {
    if (typeof value === 'number' || typeof value === 'string') lines.push(`${label(key)}: ${value}`)
  }
  return lines
}

/**
 * The task menu and the small forms it leads to (why, skip, snooze, "also log it", edit), one Sheet: bottom on a phone, right
 * side from `md`. Every choice is a 44 px button or radio row; nothing here needs a swipe.
 */
export function TaskSheet({
  task,
  mode,
  today,
  actions,
  onMode,
  onClose,
}: {
  task: Task | null
  mode: SheetMode
  /** The student's local date (`YYYY-MM-DD`), for the snooze date. */
  today: string
  actions: TaskActions
  onMode: (mode: SheetMode) => void
  onClose: () => void
}) {
  const wide = useMediaQuery('(min-width: 768px)')
  return (
    <Sheet open={task !== null} onOpenChange={(open) => !open && onClose()}>
      <SheetContent side={wide ? 'right' : 'bottom'}>
        {task ? (
          <Body task={task} mode={mode} today={today} actions={actions} onMode={onMode} onClose={onClose} />
        ) : null}
      </SheetContent>
    </Sheet>
  )
}

function Body({
  task,
  mode,
  today,
  actions,
  onMode,
  onClose,
}: {
  task: Task
  mode: SheetMode
  today: string
  actions: TaskActions
  onMode: (mode: SheetMode) => void
  onClose: () => void
}) {
  const own = task.origin === 'user'
  const open = task.state === 'suggested' || task.state === 'accepted'
  const undo = actions.canUndo(task.id)
  const [reason, setReason] = useState<SkipReason | 'none'>('none')
  const [until, setUntil] = useState<SnoozeUntil>('tomorrow')
  const [custom, setCustom] = useState<string | null>(null)
  const [logIt, setLogIt] = useState(task.manual_action?.default ?? false)
  const [title, setTitle] = useState(task.title)
  const [minutes, setMinutes] = useState(String(task.est_minutes))
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  useEffect(() => setError(null), [mode])

  const done = (fn: () => unknown) => {
    onClose()
    void fn()
  }

  if (mode === 'why') {
    const lines = whyLines(task)
    return (
      <>
        <SheetHeader>
          <SheetTitle>Why this task?</SheetTitle>
          <SheetDescription>{task.title}</SheetDescription>
        </SheetHeader>
        <p className="text-sm">{task.reason || 'Picked for you from your syllabus and revisions.'}</p>
        {lines.length ? (
          <ul className="mt-3 list-disc space-y-1 pl-5 text-sm text-muted-foreground">
            {lines.map((l) => (
              <li key={l}>{l}</li>
            ))}
          </ul>
        ) : null}
        <SheetFooter>
          <Button variant="outline" onClick={() => onMode('menu')}>
            Back
          </Button>
        </SheetFooter>
      </>
    )
  }

  if (mode === 'skip') {
    return (
      <>
        <SheetHeader>
          <SheetTitle>Skip this task</SheetTitle>
          <SheetDescription>A reason is optional. It helps us suggest better.</SheetDescription>
        </SheetHeader>
        <RadioGroup value={reason} onValueChange={(v) => setReason(v as SkipReason | 'none')} aria-label="Reason">
          {SKIP_REASONS.map((r) => (
            <RadioCardItem key={r.value} value={r.value} className="min-h-11 p-3">
              {r.label}
            </RadioCardItem>
          ))}
        </RadioGroup>
        {reason === 'not_in_attempt' ? (
          <p className="mt-3 text-sm text-muted-foreground">
            Not part of your attempt?{' '}
            <Link to="/app/settings/coverage" className="underline underline-offset-4">
              Exclude it in your coverage settings
            </Link>
            .
          </p>
        ) : null}
        <SheetFooter>
          <Button variant="outline" onClick={() => onMode('menu')}>
            Back
          </Button>
          <Button onClick={() => done(() => actions.skip(task, reason === 'none' ? null : reason))}>Skip</Button>
        </SheetFooter>
      </>
    )
  }

  if (mode === 'snooze') {
    const choice = own && custom ? custom : until
    return (
      <>
        <SheetHeader>
          <SheetTitle>Snooze this task</SheetTitle>
          <SheetDescription>
            {own ? 'It moves to that day.' : 'We will not suggest it again until then.'}
          </SheetDescription>
        </SheetHeader>
        <RadioGroup
          value={custom ? '' : until}
          onValueChange={(v) => {
            setCustom(null)
            setUntil(v as SnoozeUntil)
          }}
          aria-label="Snooze until"
        >
          {SNOOZE_CHOICES.map((c) => (
            <RadioCardItem key={c.value} value={c.value} className="min-h-11 p-3">
              {c.label}
            </RadioCardItem>
          ))}
        </RadioGroup>
        {own ? (
          <DatePicker
            className="mt-3"
            label="Or pick a day"
            value={custom}
            min={addIsoDays(today, 1)}
            max={addIsoDays(today, OWN_TASK_MAX_DAYS_AHEAD)}
            onValueChange={setCustom}
          />
        ) : null}
        <SheetFooter>
          <Button variant="outline" onClick={() => onMode('menu')}>
            Back
          </Button>
          <Button onClick={() => done(() => actions.snooze(task, choice))}>Snooze</Button>
        </SheetFooter>
      </>
    )
  }

  if (mode === 'tick' && task.manual_action) {
    return (
      <>
        <SheetHeader>
          <SheetTitle>Mark as done</SheetTitle>
          <SheetDescription>{task.title}</SheetDescription>
        </SheetHeader>
        <div className="flex min-h-11 items-center justify-between gap-4">
          <Label htmlFor="log-it">{task.manual_action.label}</Label>
          <Switch id="log-it" checked={logIt} onCheckedChange={setLogIt} />
        </div>
        <SheetFooter>
          <Button variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button onClick={() => done(() => actions.tick(task, logIt))}>Mark done</Button>
        </SheetFooter>
      </>
    )
  }

  if (mode === 'edit' && own) {
    const save = async () => {
      const trimmed = title.trim()
      const mins = Number(minutes)
      if (!trimmed) return setError('Give the task a title.')
      if (!Number.isInteger(mins) || mins < OWN_EST_MIN || mins > OWN_EST_MAX)
        return setError(`Minutes must be a whole number from ${OWN_EST_MIN} to ${OWN_EST_MAX}.`)
      setSaving(true)
      try {
        await actions.edit(task, { title: trimmed, est_minutes: mins })
        onClose()
      } catch (e) {
        setError(
          errorCode(e) === 'state_conflict'
            ? 'This task changed on another device. Close this and try again.'
            : errorMessage(e, 'That did not save. Please try again.'),
        )
      } finally {
        setSaving(false)
      }
    }
    return (
      <>
        <SheetHeader>
          <SheetTitle>Edit task</SheetTitle>
        </SheetHeader>
        <div className="space-y-4">
          <TextField label="Title" value={title} maxLength={TITLE_MAX} onChange={(e) => setTitle(e.target.value)} />
          <TextField
            label="Minutes"
            type="number"
            inputMode="numeric"
            min={OWN_EST_MIN}
            max={OWN_EST_MAX}
            value={minutes}
            onChange={(e) => setMinutes(e.target.value)}
            error={error ?? undefined}
          />
        </div>
        <SheetFooter>
          <Button variant="outline" onClick={() => onMode('menu')}>
            Back
          </Button>
          <Button loading={saving} onClick={() => void save()}>
            Save
          </Button>
        </SheetFooter>
      </>
    )
  }

  return (
    <>
      <SheetHeader>
        <SheetTitle className="line-clamp-2 text-lg">{task.title}</SheetTitle>
        <SheetDescription>Choose what to do with this task.</SheetDescription>
      </SheetHeader>
      <div className="grid gap-1">
        <MenuButton icon={<Info aria-hidden />} onClick={() => onMode('why')}>
          Why this?
        </MenuButton>
        {undo ? (
          <MenuButton icon={<Undo2 aria-hidden />} onClick={() => done(() => actions.undo(task, undo.from, undo.back))}>
            Restore
          </MenuButton>
        ) : null}
        {open && !own ? (
          <MenuButton icon={<Shuffle aria-hidden />} onClick={() => done(() => actions.swap(task))}>
            Swap for another
          </MenuButton>
        ) : null}
        {open ? (
          <MenuButton icon={<AlarmClock aria-hidden />} onClick={() => onMode('snooze')}>
            Snooze
          </MenuButton>
        ) : null}
        {open ? (
          <MenuButton icon={<SkipForward aria-hidden />} onClick={() => onMode('skip')}>
            Skip
          </MenuButton>
        ) : null}
        {own ? (
          <MenuButton icon={<Pencil aria-hidden />} onClick={() => onMode('edit')}>
            Edit
          </MenuButton>
        ) : null}
        {own ? (
          <MenuButton icon={<Trash2 aria-hidden />} onClick={() => done(() => actions.remove(task))}>
            Delete
          </MenuButton>
        ) : null}
      </div>
    </>
  )
}
