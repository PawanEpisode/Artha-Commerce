import type { PermissionView } from './permissionView'

/**
 * Follow-up ask (PRD 5.1, W2.5b): a student who chose "Not now" is asked again, but only right after a finished focus
 * round, at most twice more, 14 days apart. The server owns the spacing and the cap (`followup_due`); the page owns the
 * moment. A block, an unsupported browser or a missing install is never nagged: only `ready` can show the prompt.
 */
export interface FollowUpFacts {
  /** The notifications UI flag (fails open). */
  flagOn: boolean
  /** The server says an ask may be shown now. */
  due: boolean
  /** The browser view: only `ready` (permission undecided and push possible) can be asked. */
  view: PermissionView
  /** Focus rounds that ended during this visit to the page. */
  roundsFinished: number
}

export const shouldAskFollowUp = ({ flagOn, due, view, roundsFinished }: FollowUpFacts): boolean =>
  flagOn && due && view.kind === 'ready' && roundsFinished > 0
