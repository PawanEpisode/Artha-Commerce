import { Badge, DataTable, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@artha/design-system'
import { Link } from '@tanstack/react-router'

import { cardsText, newerText, subscriptionState, tiersText } from '../lib/decks'
import type { ApiDeck } from '../lib/schemas'

/** One deck as a table row: the title is the link, then where she stands with it, how many cards and the tier mix. */
function DeckRow({ deck }: { deck: ApiDeck }) {
  const state = subscriptionState(deck)
  const newer = deck.subscription ? newerText(deck.subscription.newer_versions) : ''
  const where = [deck.subject_name, deck.chapter_name].filter(Boolean).join(' · ')
  const mix = tiersText(deck.tiers)
  return (
    <TableRow>
      <TableCell className="max-w-0 min-w-36 py-2">
        <Link
          to="/app/recall/decks/$deckId"
          params={{ deckId: deck.id }}
          className="block truncate rounded-sm font-medium hover:underline focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
        >
          {deck.title}
        </Link>
        {where ? <p className="truncate text-xs text-muted-foreground">{where}</p> : null}
      </TableCell>
      <TableCell className="py-2">
        <div className="flex flex-wrap items-center gap-1">
          {state === 'active' ? <Badge variant="accent">Subscribed</Badge> : null}
          {state === 'active' && deck.subscription?.update_available ? (
            <Badge variant="highlight">Update available</Badge>
          ) : null}
          {state === 'archived' ? <Badge variant="outline">Unsubscribed</Badge> : null}
        </div>
        {newer ? <p className="text-xs text-muted-foreground">{newer}</p> : null}
      </TableCell>
      <TableCell className="text-right whitespace-nowrap tabular-nums">{cardsText(deck)}</TableCell>
      <TableCell className="hidden text-muted-foreground md:table-cell">{mix}</TableCell>
    </TableRow>
  )
}

/** The decks as a dense table. `label` names it for assistive tech ("Deck library", "Your decks"). */
export function DeckTable({ decks, label }: { decks: ApiDeck[]; label: string }) {
  return (
    <DataTable aria-label={label}>
      <TableHeader>
        <TableRow>
          <TableHead>Deck</TableHead>
          <TableHead>Status</TableHead>
          <TableHead className="text-right">Cards</TableHead>
          <TableHead className="hidden md:table-cell">Mix</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {decks.map((d) => (
          <DeckRow key={d.id} deck={d} />
        ))}
      </TableBody>
    </DataTable>
  )
}
