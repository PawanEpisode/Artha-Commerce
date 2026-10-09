import { Badge } from '@artha/design-system'
import { Link } from '@tanstack/react-router'

import { cardsText, newerText, subscriptionState, tiersText } from '../lib/decks'
import type { ApiDeck } from '../lib/schemas'

/** One deck in the library: what it holds, where she stands with it, and a way in. */
export function DeckCard({ deck }: { deck: ApiDeck }) {
  const state = subscriptionState(deck)
  const newer = deck.subscription ? newerText(deck.subscription.newer_versions) : ''
  const where = [deck.subject_name, deck.chapter_name].filter(Boolean).join(' · ')
  return (
    <li className="space-y-3 rounded-xl border border-border bg-card p-4 sm:p-5">
      <div className="flex flex-wrap items-center gap-2">
        {state === 'active' ? <Badge variant="accent">Subscribed</Badge> : null}
        {state === 'archived' ? <Badge variant="outline">Unsubscribed</Badge> : null}
        {where ? <span className="min-w-0 text-xs text-muted-foreground">{where}</span> : null}
      </div>
      <h3 className="font-display text-lg font-bold break-words">
        <Link
          to="/app/recall/decks/$deckId"
          params={{ deckId: deck.id }}
          className="rounded-sm hover:underline focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
        >
          {deck.title}
        </Link>
      </h3>
      {deck.description ? <p className="text-sm text-muted-foreground">{deck.description}</p> : null}
      <p className="text-sm">
        {cardsText(deck)}
        {tiersText(deck.tiers) ? <span className="text-muted-foreground"> ({tiersText(deck.tiers)})</span> : null}
      </p>
      {newer ? <p className="text-xs text-muted-foreground">{newer}</p> : null}
    </li>
  )
}
