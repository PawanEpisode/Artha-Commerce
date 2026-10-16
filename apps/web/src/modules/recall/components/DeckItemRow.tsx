import {
  Badge,
  Button,
  DataTable,
  Flag,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@artha/design-system'

import { tierLabel } from '../lib/decks'
import type { ApiDeckItem } from '../lib/schemas'
import { kindLabel } from './CardFace'

/** The items of a deck as a table: a preview line (the full card shows in revision), its kind and tier, and a way to report it. */
export function DeckItemTable({ items, onReport }: { items: ApiDeckItem[]; onReport: (item: ApiDeckItem) => void }) {
  return (
    <DataTable aria-label="Cards in this deck">
      <TableHeader>
        <TableRow>
          <TableHead>Card</TableHead>
          <TableHead className="hidden sm:table-cell">Kind</TableHead>
          <TableHead className="hidden sm:table-cell">Importance</TableHead>
          <TableHead className="w-0">
            <span className="sr-only">Actions</span>
          </TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {items.map((item) => (
          <TableRow key={item.item_id}>
            <TableCell className="max-w-0 min-w-40 py-2">
              <p className="line-clamp-2 break-words">{item.preview}</p>
              {item.under_review ? (
                <Badge variant="highlight" className="mt-1">
                  Under review after amendment
                </Badge>
              ) : null}
            </TableCell>
            <TableCell className="hidden sm:table-cell">
              <Badge variant="outline">{kindLabel(item.kind)}</Badge>
            </TableCell>
            <TableCell className="hidden sm:table-cell">
              <Badge variant={item.importance === 'mandatory' ? 'highlight' : 'default'}>
                {tierLabel(item.importance)}
              </Badge>
            </TableCell>
            <TableCell className="text-right">
              <Button
                variant="ghost"
                size="sm"
                aria-label={`Report this card: ${item.preview}`}
                onClick={() => onReport(item)}
              >
                <Flag aria-hidden />
                <span className="hidden sm:inline">Report</span>
              </Button>
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </DataTable>
  )
}
