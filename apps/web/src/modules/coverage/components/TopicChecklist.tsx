import { Badge, Card, Checkbox } from '@artha/design-system'

import type { TopicRow } from '../lib/types'

interface Props {
  topics: TopicRow[]
  /** Chapters without topics yet get one implicit "whole chapter" tick (see PRD edge cases). */
  chapterName: string
  hasTopics: boolean
  chapterDone: boolean
  onToggleTopic: (topicId: string, done: boolean) => void
  onToggleChapter: (done: boolean) => void
}

function Row({
  id,
  label,
  kind,
  checked,
  onChange,
}: {
  id: string
  label: string
  kind?: string
  checked: boolean
  onChange: (v: boolean) => void
}) {
  return (
    <li>
      <Card className="focus-within:ring-[3px] focus-within:ring-ring/40">
        <label htmlFor={id} className="flex min-h-14 cursor-pointer items-center gap-4 p-4">
          <Checkbox id={id} checked={checked} onCheckedChange={(v) => onChange(v === true)} />
          <span className={`min-w-0 flex-1 font-medium ${checked ? 'text-muted-foreground' : ''}`}>{label}</span>
          {kind && kind !== 'concept' ? <Badge variant="outline">{kind.replace('_', ' ')}</Badge> : null}
        </label>
      </Card>
    </li>
  )
}

export function TopicChecklist({ topics, chapterName, hasTopics, chapterDone, onToggleTopic, onToggleChapter }: Props) {
  if (!hasTopics) {
    return (
      <ul className="space-y-2">
        <Row id="chapter-read" label={`I have read ${chapterName}`} checked={chapterDone} onChange={onToggleChapter} />
      </ul>
    )
  }
  return (
    <ul className="space-y-2">
      {topics.map((t) => (
        <Row
          key={t.id}
          id={`topic-${t.id}`}
          label={t.name}
          kind={t.kind}
          checked={t.is_done}
          onChange={(v) => onToggleTopic(t.id, v)}
        />
      ))}
    </ul>
  )
}
