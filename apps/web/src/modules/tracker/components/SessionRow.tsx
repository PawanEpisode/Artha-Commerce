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
  TableCell,
  TableRow,
  Trash2,
} from '@artha/design-system'

import { ALL_CHAPTERS_LABEL } from '~/modules/coverage'

import { formatDuration } from '../lib/duration'
import { activityLabel, timeOfDay } from '../lib/format'
import type { StudySession } from '../lib/types'

interface Props {
  session: StudySession
  tz: string
  selected: boolean
  /** Merge only makes sense inside one day, so a row of another day cannot be ticked while a selection exists. */
  selectDisabled?: boolean
  onSelect: (selected: boolean) => void
  onEdit: () => void
  onSplit: () => void
  onDelete: () => void
}

export const SOURCE_LABEL: Record<string, string> = {
  pomodoro: 'Pomodoro',
  stopwatch: 'Stopwatch',
  manual: 'Manual',
  auto: 'Auto',
}

/** One logged session as a table row: times, subject and chapter, flags as words, the activity, counted time and its actions. */
export function SessionRow({ session: s, tz, selected, selectDisabled, onSelect, onEdit, onSplit, onDelete }: Props) {
  const title = s.subject_name || 'No subject'
  // A subject with no chapter is the whole subject; say so instead of leaving the chapter blank.
  const chapterText = s.chapter_name || (s.subject_id ? ALL_CHAPTERS_LABEL : '')
  const flags = [
    s.is_edited ? (
      <Badge key="edited" variant="outline">
        Edited
      </Badge>
    ) : null,
    s.merged_count > 1 ? (
      <Badge key="merged" variant="outline">
        Merged from {s.merged_count}
      </Badge>
    ) : null,
    s.overlaps_other ? (
      <Badge key="overlap" variant="highlight">
        Overlaps other time
      </Badge>
    ) : null,
    s.idle_trimmed ? (
      <Badge key="idle" variant="outline">
        Idle time removed
      </Badge>
    ) : null,
  ].filter(Boolean)
  return (
    <TableRow data-state={selected ? 'selected' : undefined}>
      <TableCell className="w-8 pr-0">
        <Checkbox
          checked={selected}
          disabled={selectDisabled && !selected}
          onCheckedChange={(c) => onSelect(c === true)}
          aria-label={`Select ${title}, ${timeOfDay(s.started_at, tz)}`}
        />
      </TableCell>
      <TableCell className="whitespace-nowrap text-muted-foreground tabular-nums">
        {timeOfDay(s.started_at, tz)} to {timeOfDay(s.ended_at, tz)}
      </TableCell>
      <TableCell className="max-w-0 min-w-32 py-1.5">
        <p className="truncate">
          <span className="font-medium">{title}</span>
          {chapterText ? <span className="text-muted-foreground"> · {chapterText}</span> : null}
        </p>
        {flags.length > 0 || s.note ? (
          <div className="mt-0.5 flex flex-wrap items-center gap-1">
            {flags}
            {s.note ? <span className="truncate text-xs text-muted-foreground">{s.note}</span> : null}
          </div>
        ) : null}
      </TableCell>
      <TableCell className="hidden text-muted-foreground sm:table-cell">{activityLabel(s.activity_type)}</TableCell>
      <TableCell className="hidden md:table-cell">
        <Badge variant="outline">{SOURCE_LABEL[s.source] ?? s.source}</Badge>
      </TableCell>
      <TableCell className="text-right font-medium whitespace-nowrap tabular-nums">
        {formatDuration(s.focus_seconds)}
      </TableCell>
      <TableCell className="w-8 pl-0 text-right">
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="ghost" size="icon-sm" aria-label={`Actions for ${title}, ${timeOfDay(s.started_at, tz)}`}>
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
      </TableCell>
    </TableRow>
  )
}
