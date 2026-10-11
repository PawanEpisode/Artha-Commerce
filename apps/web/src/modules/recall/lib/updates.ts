/** Words and small rules for living decks (R2-W2). Pure, so they are tested without a screen. */
import type { ChapterRemapItem, SyncResult, UpdatePreview } from './schemas'

export const KIND_ORDER = ['amendment', 'substantive', 'added', 'removed', 'clarify', 'typo'] as const

export const KIND_LABEL: Record<(typeof KIND_ORDER)[number], string> = {
  amendment: 'Changed after a law amendment',
  substantive: 'Meaning changed',
  added: 'New cards',
  removed: 'Removed',
  clarify: 'Clearer wording',
  typo: 'Typo fixes',
}

const plural = (n: number, one: string, many: string) => `${n} ${n === 1 ? one : many}`

export const changesText = (n: number): string => plural(n, 'change', 'changes')

/** The kinds that have at least one change, most serious first. */
export const kindsIn = (counts: Record<string, number>): (typeof KIND_ORDER)[number][] =>
  KIND_ORDER.filter((k) => (counts[k] ?? 0) > 0)

/** Title of the banner on a deck she follows or has pinned. */
export function bannerTitle(changes: number): string {
  return changes > 0 ? `Update available (${changesText(changes)})` : 'Update available'
}

export function bannerHelp(follow: boolean): string {
  return follow
    ? 'It will be applied for you shortly. You can apply it now.'
    : 'You have pinned this deck, so nothing changes until you apply it.'
}

/** What the card carries until she taps "Still correct". */
export function recheckLabel(reason: string | null): string {
  return reason === 'amendment' ? 'Check against the amendment' : 'Updated, please re-check'
}

export function recheckHelp(reason: string | null): string {
  return reason === 'amendment'
    ? 'A law this card relies on was amended. Your memory of it is untouched. Read it once and confirm.'
    : 'The deck changed the meaning of this card, so it comes back a little sooner. Read it once and confirm.'
}

export function appliedMessage(r: SyncResult): string {
  if (!r.changed) return 'You already have the latest version.'
  const parts = [
    r.cards_created > 0 ? plural(r.cards_created, 'new card', 'new cards') : '',
    r.cards_reset > 0 ? `${plural(r.cards_reset, 'card', 'cards')} to re-check` : '',
    r.cards_archived > 0 ? `${plural(r.cards_archived, 'card', 'cards')} removed` : '',
  ].filter(Boolean)
  return parts.length > 0 ? `Updated: ${parts.join(', ')}.` : 'Updated.'
}

export const returningText = (n: number): string =>
  n > 0 ? `${plural(n, 'card comes', 'cards come')} back today to be re-checked.` : ''

/** Items named per kind, then "and N more" when the server held some back. */
export function moreText(preview: Pick<UpdatePreview, 'more'>, kind: string): string {
  const n = preview.more[kind] ?? 0
  return n > 0 ? `and ${n} more` : ''
}

export function relationText(relation: string): string {
  switch (relation) {
    case 'split':
      return 'This chapter was split in the new syllabus.'
    case 'merged':
      return 'This chapter was merged into another.'
    case 'none':
      return 'This chapter has no match in the new syllabus.'
    default:
      return 'This chapter changed in the new syllabus.'
  }
}

export const remapSummary = (items: Pick<ChapterRemapItem, 'card_count'>[]): string =>
  plural(items.length, 'topic needs', 'topics need') + ' a chapter of your new syllabus'
