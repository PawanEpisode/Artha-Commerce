import {
  Badge,
  Checkbox,
  DataTable,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@artha/design-system'
import { Link } from '@tanstack/react-router'

import { dueLabel, STATE_LABELS } from '../lib/format'
import { plain } from '../lib/inline'
import type { RecallCardRow } from '../lib/schemas'
import { kindLabel } from './CardFace'

const BADGE_TEXT: Record<string, string> = {
  suspended: 'Paused',
  tricky: 'Tricky',
  recheck: 'Needs a look',
  updated: 'Updated',
  amendment: 'Check against amendment',
  buried: 'Back tomorrow',
}

/** One card as a table row: tick box, the front as the link, kind, chapter, status, due and how often it was reviewed. */
function CardTableRow({
  card,
  selected,
  onSelect,
}: {
  card: RecallCardRow
  selected: boolean
  onSelect: (id: string, on: boolean) => void
}) {
  const text = plain(card.front_md).slice(0, 140) || 'Untitled card'
  const flags = [
    ...(card.needs_recheck
      ? [{ key: 'recheck', text: card.recheck_reason === 'amendment' ? BADGE_TEXT.amendment : BADGE_TEXT.updated }]
      : []),
    ...card.badges
      .filter((b) => !(card.needs_recheck && b === 'recheck'))
      .map((b) => ({ key: b, text: BADGE_TEXT[b] ?? b })),
  ]
  return (
    <TableRow data-state={selected ? 'selected' : undefined}>
      <TableCell className="w-8 pr-0">
        <Checkbox
          checked={selected}
          onCheckedChange={(v) => onSelect(card.id, v === true)}
          aria-label={`Select: ${text}`}
        />
      </TableCell>
      <TableCell className="max-w-0 min-w-40">
        <Link
          to="/app/recall/cards/$cardId"
          params={{ cardId: card.id }}
          className="block truncate font-medium text-foreground underline-offset-4 hover:underline focus-visible:underline"
        >
          {text}
        </Link>
      </TableCell>
      <TableCell className="hidden sm:table-cell">
        <Badge variant="outline">{kindLabel(card.kind)}</Badge>
      </TableCell>
      <TableCell className="hidden max-w-48 truncate text-muted-foreground lg:table-cell">
        {card.chapter?.name ?? ''}
      </TableCell>
      <TableCell>
        <div className="flex flex-wrap items-center gap-1">
          <span className="text-muted-foreground">{STATE_LABELS[card.state] ?? card.state_name}</span>
          {flags.map((f) => (
            <Badge key={f.key} variant={f.key === 'recheck' ? 'highlight' : 'outline'}>
              {f.text}
            </Badge>
          ))}
        </div>
      </TableCell>
      <TableCell className="hidden text-right whitespace-nowrap text-muted-foreground tabular-nums md:table-cell">
        {dueLabel(card.due_at)}
      </TableCell>
      <TableCell className="hidden text-right text-muted-foreground tabular-nums md:table-cell">{card.reps}</TableCell>
      <TableCell className="hidden text-right text-muted-foreground tabular-nums md:table-cell">
        {card.lapses}
      </TableCell>
    </TableRow>
  )
}

/** The student's cards as a dense table with a select-all box in the header. `label` names the table for assistive tech. */
export function CardTable({
  cards,
  picked,
  onSelect,
  onSelectAll,
  label = 'Cards',
}: {
  cards: RecallCardRow[]
  picked: ReadonlySet<string>
  onSelect: (id: string, on: boolean) => void
  onSelectAll: (on: boolean) => void
  label?: string
}) {
  const all = cards.length > 0 && picked.size >= cards.length
  return (
    <DataTable aria-label={label}>
      <TableHeader>
        <TableRow>
          <TableHead className="w-8 pr-0">
            <Checkbox
              checked={all}
              onCheckedChange={(v) => onSelectAll(v === true)}
              aria-label="Select all cards shown"
            />
          </TableHead>
          <TableHead>Card</TableHead>
          <TableHead className="hidden sm:table-cell">Kind</TableHead>
          <TableHead className="hidden lg:table-cell">Chapter</TableHead>
          <TableHead>Status</TableHead>
          <TableHead className="hidden text-right md:table-cell">Due</TableHead>
          <TableHead className="hidden text-right md:table-cell">Reviews</TableHead>
          <TableHead className="hidden text-right md:table-cell">Lapses</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {cards.map((c) => (
          <CardTableRow key={c.id} card={c} selected={picked.has(c.id)} onSelect={onSelect} />
        ))}
      </TableBody>
    </DataTable>
  )
}
