import { Badge, DataTable, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@artha/design-system'

import type { ForgottenCard } from '../lib/schemas'
import { kindLabel } from './CardFace'
import { InlineText } from './InlineText'

const times = (n: number) => (n === 1 ? 'once' : `${n} times`)

/**
 * The cards the student keeps missing, as a table: the question, its kind and subject, how often it was missed recently
 * and how often it was forgotten after she knew it.
 */
export function ForgottenTable({ items, label = 'Cards slipping away' }: { items: ForgottenCard[]; label?: string }) {
  return (
    <DataTable aria-label={label}>
      <TableHeader>
        <TableRow>
          <TableHead>Card</TableHead>
          <TableHead className="hidden sm:table-cell">Kind</TableHead>
          <TableHead className="hidden md:table-cell">Subject</TableHead>
          <TableHead className="text-right">Missed</TableHead>
          <TableHead className="hidden text-right sm:table-cell">Forgotten</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {items.map((item) => (
          <TableRow key={item.card_id}>
            <TableCell className="max-w-0 min-w-40 py-2">
              <div className="line-clamp-2 break-words [&_p]:text-balance">
                <InlineText text={item.front_md} />
              </div>
            </TableCell>
            <TableCell className="hidden sm:table-cell">
              <Badge variant="outline">{kindLabel(item.kind)}</Badge>
            </TableCell>
            <TableCell className="hidden text-muted-foreground md:table-cell">{item.subject_key ?? ''}</TableCell>
            <TableCell className="text-right whitespace-nowrap tabular-nums">
              <span className="sr-only">Missed {times(item.agains)} recently</span>
              <span aria-hidden>{times(item.agains)}</span>
            </TableCell>
            <TableCell className="hidden text-right whitespace-nowrap text-muted-foreground tabular-nums sm:table-cell">
              {item.lapses > 0 ? times(item.lapses) : ''}
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </DataTable>
  )
}
