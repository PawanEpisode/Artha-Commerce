import {
  Badge,
  Button,
  Checkbox,
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
  Ellipsis,
  Pencil,
  Scissors,
  Trash2,
} from '@artha/design-system'

import { formatDuration } from '../lib/duration'
import { activityLabel, timeOfDay } from '../lib/format'
import type { StudySession } from '../lib/types'

interface Props {
  session: StudySession
  tz: string
  selected: boolean
  onSelect: (selected: boolean) => void
  onEdit: () => void
  onSplit: () => void
  onDelete: () => void
}

const SOURCE_LABEL: Record<string, string> = {
  pomodoro: 'Pomodoro',
  stopwatch: 'Stopwatch',
  manual: 'Manual',
  auto: 'Auto',
}

/** One logged session: times, tags, counted minutes and its actions. Flags are words, not colour. */
export function SessionRow({ session: s, tz, selected, onSelect, onEdit, onSplit, onDelete }: Props) {
  const title = s.subject_name || 'No subject'
  return (
    <li className="flex items-start gap-3 rounded-xl border border-border bg-card p-3">
      <Checkbox
        className="mt-1.5"
        checked={selected}
        onCheckedChange={(c) => onSelect(c === true)}
        aria-label={`Select ${title}, ${timeOfDay(s.started_at, tz)}`}
      />
      <div className="min-w-0 flex-1 space-y-1">
        <p className="font-semibold">
          {title}
          {s.chapter_name ? <span className="font-normal text-muted-foreground"> · {s.chapter_name}</span> : null}
        </p>
        <p className="text-sm text-muted-foreground">
          {timeOfDay(s.started_at, tz)} to {timeOfDay(s.ended_at, tz)} · {activityLabel(s.activity_type)}
        </p>
        <div className="flex flex-wrap gap-1.5">
          <Badge variant="outline">{SOURCE_LABEL[s.source] ?? s.source}</Badge>
          {s.is_edited ? <Badge variant="outline">Edited</Badge> : null}
          {s.merged_count > 1 ? <Badge variant="outline">Merged from {s.merged_count}</Badge> : null}
          {s.overlaps_other ? <Badge variant="highlight">Overlaps other time</Badge> : null}
          {s.idle_trimmed ? <Badge variant="outline">Idle time removed</Badge> : null}
        </div>
        {s.note ? <p className="text-sm">{s.note}</p> : null}
      </div>
      <p className="font-display text-lg font-bold tabular-nums">{formatDuration(s.focus_seconds)}</p>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button variant="ghost" size="icon" aria-label={`Actions for ${title}, ${timeOfDay(s.started_at, tz)}`}>
            <Ellipsis aria-hidden />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end">
          <DropdownMenuItem onSelect={onEdit}>
            <Pencil aria-hidden /> Edit
          </DropdownMenuItem>
          {s.source !== 'pomodoro' ? (
            <DropdownMenuItem onSelect={onSplit}>
              <Scissors aria-hidden /> Split
            </DropdownMenuItem>
          ) : null}
          <DropdownMenuItem onSelect={onDelete}>
            <Trash2 aria-hidden /> Delete
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    </li>
  )
}
