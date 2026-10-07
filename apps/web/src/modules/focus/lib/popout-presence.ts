import { nowMs } from '~/modules/tracker'

import { type PopoutPresence, presenceAfterTap, presenceFlags } from './popout'

/**
 * What the timer read needs to know about the floating window, kept outside React like the tracker's clock because
 * the read (`fetchTimerState`) is a plain function. The window hook says when it opens, hides and closes; the timer
 * owner says when the running phase reaches its target; taps in the window are recorded as they happen.
 */
let open = false
let visible = true
let presence: PopoutPresence = { targetMs: null, tapMs: null }

export const setPopoutOpen = (next: boolean) => {
  open = next
  if (!next) visible = true
}
export const setPopoutVisible = (next: boolean) => {
  visible = next
}

/** A new target (a new round, a resume, a pause) starts a fresh presence window; the same target keeps its tap. */
export function setPresenceTarget(targetMs: number | null) {
  if (targetMs !== presence.targetMs) presence = { targetMs, tapMs: null }
}

/** A pointer press or key press in the window. */
export function recordPopoutTap(at = nowMs()) {
  presence = presenceAfterTap(presence, at)
}

/** The three facts `popoutAlive` takes from the window. */
export function popoutPresence(at = nowMs()) {
  return { popoutOpen: open && visible, ...presenceFlags(presence, at) }
}

export function resetPopoutPresence() {
  open = false
  visible = true
  presence = { targetMs: null, tapMs: null }
}
