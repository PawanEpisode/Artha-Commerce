import { z } from 'zod'

import { CARD_KINDS } from './cardKinds'

const uuid = z.string().uuid().optional().catch(undefined)
const text = (max: number) => z.string().max(max).optional().catch(undefined)

export const CARD_STATES = ['new', 'learning', 'review', 'suspended', 'tricky', 'recheck'] as const
export const CARD_SORTS = ['newest', 'oldest', 'updated'] as const

/** `/app/recall/cards`: every filter lives in the URL, so a view can be shared, bookmarked and reloaded. */
export const cardsSearchSchema = z.object({
  q: text(200),
  kind: z.enum(CARD_KINDS).optional().catch(undefined),
  tier: z.enum(['bullet', 'important', 'mandatory']).optional().catch(undefined),
  state: z.enum(CARD_STATES).optional().catch(undefined),
  chapter: uuid,
  deck: uuid,
  sort: z.enum(CARD_SORTS).optional().catch(undefined),
})
export type CardsSearch = z.infer<typeof cardsSearchSchema>

/** `/app/recall/cards/new`: what Notes, the reader and a chapter page can hand over. */
export const newCardSearchSchema = z.object({
  kind: z.enum(CARD_KINDS).optional().catch(undefined),
  chapter: uuid,
  topic: uuid,
  deck: uuid,
  from: z.enum(['selection']).optional().catch(undefined),
  draft: text(8000),
})
export type NewCardSearch = z.infer<typeof newCardSearchSchema>

/** The API's query names for the URL's. */
export function listParams(s: CardsSearch): Record<string, string | undefined> {
  return {
    q: s.q?.trim() || undefined,
    kind: s.kind,
    tier: s.tier,
    state: s.state,
    chapter_id: s.chapter,
    deck_id: s.deck,
    sort: s.sort && s.sort !== 'newest' ? s.sort : undefined,
  }
}

export const hasFilters = (s: CardsSearch): boolean => Object.values(listParams(s)).some((v) => v !== undefined)
