import {
  Badge,
  DataTable,
  ReadToggle,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@artha/design-system'
import { useId } from 'react'

import type { TopicRow } from '../lib/types'

interface Props {
  topics: TopicRow[]
  /** Chapters without topics yet get one implicit "whole chapter" toggle (see PRD edge cases). */
  chapterName: string
  hasTopics: boolean
  chapterDone: boolean
  onToggleTopic: (topicId: string, done: boolean) => void
  onToggleChapter: (done: boolean) => void
}

/**
 * One table row per topic: the name (wraps, never overflows), its kind, and a compact "Mark as read" toggle that turns into
 * a tick and "Read". The write is optimistic; the toggle is a real button (`aria-pressed`), so Space and Enter work.
 */
function Row({
  label,
  kind,
  checked,
  toggleLabels,
  onChange,
}: {
  label: string
  kind?: string
  checked: boolean
  toggleLabels?: { unchecked: string; checked: string }
  onChange: (done: boolean) => void
}) {
  const titleId = useId()
  return (
    <TableRow>
      <TableCell className="min-w-48 py-1.5 whitespace-normal">
        <span id={titleId} className={checked ? 'break-words text-muted-foreground' : 'font-medium break-words'}>
          {label}
        </span>
      </TableCell>
      <TableCell className="hidden sm:table-cell">
        {kind && kind !== 'concept' ? <Badge variant="outline">{kind.replace('_', ' ')}</Badge> : null}
      </TableCell>
      <TableCell className="w-px text-right">
        <ReadToggle
          checked={checked}
          onChange={onChange}
          labels={toggleLabels}
          aria-describedby={titleId}
          className="min-h-7 rounded-md px-2.5 text-xs pointer-coarse:min-h-10 [&_svg]:size-3.5 [&>span:first-child]:size-3.5"
        />
      </TableCell>
    </TableRow>
  )
}

export function TopicChecklist({ topics, chapterName, hasTopics, chapterDone, onToggleTopic, onToggleChapter }: Props) {
  return (
    <DataTable aria-label="Topics">
      <TableHeader>
        <TableRow>
          <TableHead>Topic</TableHead>
          <TableHead className="hidden sm:table-cell">Kind</TableHead>
          <TableHead className="text-right">Read</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {hasTopics ? (
          topics.map((t) => (
            <Row key={t.id} label={t.name} kind={t.kind} checked={t.is_done} onChange={(v) => onToggleTopic(t.id, v)} />
          ))
        ) : (
          <Row
            label={`I have read ${chapterName}`}
            checked={chapterDone}
            toggleLabels={{ unchecked: 'Mark chapter as read', checked: 'Chapter read' }}
            onChange={onToggleChapter}
          />
        )}
      </TableBody>
    </DataTable>
  )
}
