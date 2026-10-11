/** Words for the update history and a card's "what changed" (R2-W4). Pure, so the sentences are tested without a screen. */
import { plural } from './format'
import type { CardVersionRow, UpdateHistoryRow } from './schemas'

export const CHANGE_KIND_LABEL: Record<string, string> = {
  create: 'First version',
  typo: 'Typo fixed',
  clarify: 'Clearer wording',
  substantive: 'Meaning changed',
  amendment: 'Changed after a law amendment',
}

export const changeKindLabel = (kind: string): string => CHANGE_KIND_LABEL[kind] ?? 'Changed'

/** Why a card came back for a re-check, in her words. */
export const RESET_REASON_LABEL: Record<string, string> = {
  substantive: 'The deck changed what this card means',
  amendment: 'A law this card relies on was amended',
  typo_free: 'The wording was tidied',
}

export const resetReasonLabel = (reason: string): string => RESET_REASON_LABEL[reason] ?? 'The card was updated'

export const triggerLabel = (trigger: UpdateHistoryRow['trigger']): string =>
  trigger === 'manual' ? 'You applied it' : 'Applied for you'

/** "Version 2 to version 5 (2 versions skipped)". */
export function versionsText(
  row: Pick<UpdateHistoryRow, 'from_version_no' | 'to_version_no' | 'versions_skipped'>,
): string {
  const base = `Version ${row.from_version_no} to version ${row.to_version_no}`
  return row.versions_skipped > 0 ? `${base} (${plural(row.versions_skipped, 'version')} in between)` : base
}

/** What an update did to her cards, as a short sentence. Empty when it changed none of them. */
export function countsText(counts: Record<string, number>): string {
  const parts = [
    (counts.cards_created ?? 0) > 0 ? plural(counts.cards_created ?? 0, 'new card') : '',
    (counts.cards_restored ?? 0) > 0 ? `${plural(counts.cards_restored ?? 0, 'card')} brought back` : '',
    (counts.rechecked ?? 0) > 0 ? `${plural(counts.rechecked ?? 0, 'card')} to re-check` : '',
    (counts.silent ?? 0) > 0 ? `${plural(counts.silent ?? 0, 'card')} reworded` : '',
    (counts.cards_archived ?? 0) > 0 ? `${plural(counts.cards_archived ?? 0, 'card')} removed` : '',
  ].filter(Boolean)
  return parts.length > 0 ? `${parts.join(', ')}.` : 'None of your cards changed.'
}

/** "12 Oct 2026" from an ISO instant, in the device's zone (the day she saw it). */
export function dayText(iso: string): string {
  return new Date(iso).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' })
}

/** The status line of a version: what she has and what is waiting. */
export function versionStatus(v: CardVersionRow): string {
  if (v.current) return 'Your card shows this version'
  return v.received ? 'An earlier version' : 'Not applied yet'
}

export function waitingText(waiting: number): string {
  return waiting > 0
    ? `${plural(waiting, 'newer version')} of this card ${waiting === 1 ? 'is' : 'are'} waiting in the deck. Apply the update to get ${waiting === 1 ? 'it' : 'them'}.`
    : ''
}

/** The statement a selection card carries, in plain words. */
export function attestationText(attested: boolean): { title: string; help: string } {
  return attested
    ? {
        title: 'You said these are your own words',
        help: 'This card can be included when you share a deck. You can take that back at any time.',
      }
    : {
        title: 'Are these your own words?',
        help: 'A card made from your notes, a solution or a mistake stays private. If you rewrote it in your own words, say so and it can be included when you share a deck.',
      }
}
