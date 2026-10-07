import type { DigestState } from './schemas'

/**
 * Which digest card a page shows (W3.7, FR-N34). Pure. The inbox only ever shows the offer; the settings page shows the
 * offer when it is due and, once the digest is on, a card to switch back. Nothing at all while the data is loading or
 * the feature is off.
 */
export type DigestCard = 'offer' | 'status' | 'none'

export function digestCard(state: DigestState | undefined, place: 'settings' | 'inbox', flagOn: boolean): DigestCard {
  if (!flagOn || !state) return 'none'
  if (state.offer && !state.enabled) return 'offer'
  if (place === 'settings' && state.enabled) return 'status'
  return 'none'
}

/** What the card says once the student has answered (spoken politely, focus moves to it). */
export function digestDoneMessage(answer: 'accept' | 'decline' | 'stop', time: string): string {
  if (answer === 'accept')
    return `Done. One digest a day at ${time} from now on, and timer alerts still come straight away. You can switch back in Settings.`
  if (answer === 'stop') return 'Separate alerts are back on. You can choose what to hear about below.'
  return 'No change. You keep getting separate alerts.'
}
