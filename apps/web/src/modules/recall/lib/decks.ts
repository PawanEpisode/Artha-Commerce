/** Words and small rules for the platform decks screens. Pure, so they are tested without a screen. */
import type { ReportReason, Tier } from './api'
import type { ApiDeck, SubscribeResult } from './schemas'

export const TIER_LABEL: Record<Tier, string> = {
  mandatory: 'Must know',
  important: 'Important',
  bullet: 'Good to know',
}

export const TIER_FILTER_OPTIONS = [
  { value: '', label: 'All cards' },
  { value: 'important', label: 'Important and must know' },
  { value: 'mandatory', label: 'Must know only' },
] as const

export const REPORT_REASON_OPTIONS: ReadonlyArray<{ value: ReportReason; label: string }> = [
  { value: 'wrong', label: 'This is wrong' },
  { value: 'outdated', label: 'This is out of date' },
  { value: 'copyright', label: 'This copies someone else’s work' },
  { value: 'other', label: 'Something else' },
]

export const REPORT_NOTE_MAX = 500

export const isTier = (value: string): value is Tier =>
  value === 'bullet' || value === 'important' || value === 'mandatory'

export const tierLabel = (value: string): string => (isTier(value) ? TIER_LABEL[value] : value)

const plural = (n: number, one: string, many: string) => `${n} ${n === 1 ? one : many}`

/** "5 cards from 3 items" is more than a student needs: cards are what she will review. */
export const cardsText = (deck: Pick<ApiDeck, 'card_count'>): string => plural(deck.card_count, 'card', 'cards')

export function tiersText(tiers: ApiDeck['tiers']): string {
  return [
    tiers.mandatory > 0 ? `${tiers.mandatory} must know` : '',
    tiers.important > 0 ? `${tiers.important} important` : '',
    tiers.bullet > 0 ? `${tiers.bullet} good to know` : '',
  ]
    .filter(Boolean)
    .join(', ')
}

/** R1 shows newer versions as a count only; nothing is pulled in until the student asks for it in a later release. */
export function newerText(count: number): string {
  if (count <= 0) return ''
  return count === 1 ? 'A newer version exists' : `${count} newer versions exist`
}

export type SubscriptionState = 'none' | 'active' | 'archived'
export const subscriptionState = (deck: Pick<ApiDeck, 'subscription'>): SubscriptionState =>
  deck.subscription === null ? 'none' : deck.subscription.status

export function subscribeMessage(result: SubscribeResult): string {
  if (!result.created) return 'You already have this deck.'
  if (result.cards_restored > 0 && result.cards_created === 0) {
    return `Welcome back. ${plural(result.cards_restored, 'card is', 'cards are')} back with your progress.`
  }
  return `${plural(result.cards_created, 'card', 'cards')} added to your revision.`
}

/** The server refuses a deck over its cap whole, with the numbers; say it in a sentence. */
export function tooLargeText(body: unknown): string | null {
  const err = (body as { error?: { code?: unknown; extra?: { cards?: unknown; limit?: unknown } } } | undefined)?.error
  if (err?.code !== 'deck_too_large') return null
  const { cards, limit } = err.extra ?? {}
  return typeof cards === 'number' && typeof limit === 'number'
    ? `This deck has ${cards} cards and a deck can add up to ${limit}. Try “Must know only” or “Important and must know”.`
    : 'This deck is too large to add in one go. Try “Must know only”.'
}
