import {
  Alert,
  Badge,
  Button,
  DataTable,
  SelectField,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@artha/design-system'
import { type ReactNode, useState } from 'react'

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

/** One of her own cards waiting for a chapter of the new syllabus, as a table row. The map's candidates come first. */
export function ChapterRemapRow({ item, chapters, pending, error, onChoose }: Props) {
  const options = item.candidates.length > 0 ? item.candidates : chapters
  const [chapterId, setChapterId] = useState(options[0]?.id ?? '')
  const label = item.label || 'Untitled card'
  return (
    <TableRow className="align-top max-md:flex max-md:flex-col">
      <TableCell className="h-auto min-w-0 space-y-1 py-2.5 align-top md:w-1/2">
        <p className="font-medium break-words">{label}</p>
        <p className="flex flex-wrap items-center gap-1.5 text-xs text-muted-foreground">
          {item.from_chapter ? <Badge variant="outline">Was: {item.from_chapter.name}</Badge> : null}
          <span>{relationText(item.relation)}</span>
        </p>
      </TableCell>
      <TableCell className="h-auto min-w-0 space-y-1.5 py-2.5 align-top">
        <SelectField
          aria-label={`Move to chapter: ${label}`}
          className="w-full"
          value={chapterId}
          onValueChange={setChapterId}
          options={options.map((c) => ({ value: c.id, label: c.name }))}
        />
        {error ? <Alert variant="error">{error}</Alert> : null}
      </TableCell>
      <TableCell className="h-auto py-2.5 align-top md:w-0">
        <Button size="sm" loading={pending} disabled={!chapterId} onClick={() => onChoose(chapterId)}>
          Move card
        </Button>
      </TableCell>
    </TableRow>
  )
}

/** The rows' table. Under 768px each row stacks, so the select keeps its full width. */
export function ChapterRemapTable({ children }: { children: ReactNode }) {
  return (
    <DataTable aria-label="Cards waiting for a chapter">
      <TableHeader className="max-md:sr-only">
        <TableRow>
          <TableHead>Card</TableHead>
          <TableHead>New chapter</TableHead>
          <TableHead>
            <span className="sr-only">Action</span>
          </TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>{children}</TableBody>
    </DataTable>
  )
}
