import { Alert, Badge, Button, SelectField } from '@artha/design-system'
import { useState } from 'react'

import type { ChapterRemapItem } from '../lib/schemas'
import { relationText } from '../lib/updates'

interface Props {
  item: ChapterRemapItem
  /** Every chapter of the new scheme, offered when the map has no suggestion. */
  chapters: { id: string; name: string }[]
  pending: boolean
  error: string | null
  onChoose: (chapterId: string) => void
}

/** One of her own cards waiting for a chapter of the new syllabus. The map's candidates come first. */
export function ChapterRemapRow({ item, chapters, pending, error, onChoose }: Props) {
  const options = item.candidates.length > 0 ? item.candidates : chapters
  const [chapterId, setChapterId] = useState(options[0]?.id ?? '')
  const labelId = `remap-${item.id}`
  return (
    <li className="space-y-3 rounded-xl border border-border bg-card p-3 sm:p-4">
      <p className="text-sm font-medium break-words">{item.label || 'Untitled card'}</p>
      <p className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
        {item.from_chapter ? <Badge variant="outline">Was: {item.from_chapter.name}</Badge> : null}
        <span>{relationText(item.relation)}</span>
      </p>
      <div className="grid gap-2 sm:max-w-sm">
        <label htmlFor={labelId} className="text-sm font-medium">
          Move to chapter
        </label>
        <SelectField
          id={labelId}
          value={chapterId}
          onValueChange={setChapterId}
          options={options.map((c) => ({ value: c.id, label: c.name }))}
        />
      </div>
      {error ? <Alert variant="error">{error}</Alert> : null}
      <Button size="sm" loading={pending} disabled={!chapterId} onClick={() => onChoose(chapterId)}>
        Move card
      </Button>
    </li>
  )
}
