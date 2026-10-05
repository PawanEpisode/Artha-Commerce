import { Badge, ReadToggle } from '@artha/design-system'
import { useId } from 'react'

import { EntityListRow, EntityTitle } from '~/modules/syllabus'

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
 * One row per topic: amber rail, the topic name (wraps, never overflows) and a "Mark as read" toggle that turns into
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
    <li>
      <EntityListRow kind="topic" className="flex flex-wrap items-center gap-x-3 gap-y-2 p-3 pl-4 sm:p-4">
        <span className="min-w-0 flex-1 basis-40 space-y-1">
          <EntityTitle id={titleId} className={checked ? 'font-medium text-muted-foreground' : 'font-medium'}>
            {label}
          </EntityTitle>
          {kind && kind !== 'concept' ? <Badge variant="outline">{kind.replace('_', ' ')}</Badge> : null}
        </span>
        <ReadToggle checked={checked} onChange={onChange} labels={toggleLabels} aria-describedby={titleId} />
      </EntityListRow>
    </li>
  )
}

export function TopicChecklist({ topics, chapterName, hasTopics, chapterDone, onToggleTopic, onToggleChapter }: Props) {
  if (!hasTopics) {
    return (
      <ul className="space-y-2">
        <Row
          label={`I have read ${chapterName}`}
          checked={chapterDone}
          toggleLabels={{ unchecked: 'Mark chapter as read', checked: 'Chapter read' }}
          onChange={onToggleChapter}
        />
      </ul>
    )
  }
  return (
    <ul className="space-y-2">
      {topics.map((t) => (
        <Row key={t.id} label={t.name} kind={t.kind} checked={t.is_done} onChange={(v) => onToggleTopic(t.id, v)} />
      ))}
    </ul>
  )
}
