/**
 * The task state machine, mirrored from apps/api/modules/today/domain/states.py. The shared cases in
 * apps/api/modules/today/tests/fixtures/state_transitions.json run against both (transitions.test.ts here, the API's own tests there),
 * so the optimistic UI cannot drift from the server.
 */
import type { ActionName, TaskOrigin, TaskState } from './types'

export const ACTIONS: readonly ActionName[] = [
  'start',
  'pin',
  'complete_manual',
  'complete_event',
  'skip',
  'swap',
  'snooze',
  'expire',
  'restore',
  'undo',
  'move',
]

const TARGET: Record<string, TaskState> = {
  start: 'accepted',
  pin: 'accepted',
  complete_manual: 'done',
  complete_event: 'done',
  skip: 'skipped',
  swap: 'skipped',
  snooze: 'snoozed',
  expire: 'expired',
  restore: 'suggested',
  move: 'suggested',
}

const FROM_OPEN = ['complete_manual', 'complete_event', 'skip', 'swap', 'snooze', 'expire']
const RULES: Record<TaskState, readonly string[]> = {
  suggested: [...FROM_OPEN, 'start', 'pin'],
  accepted: FROM_OPEN,
  done: ['undo'],
  skipped: ['restore', 'expire'],
  snoozed: ['move', 'expire'],
  expired: ['complete_event'],
}

export type TransitionError = { error: 'invalid_transition'; allowed: ActionName[] } | { error: 'undo_expired' }
export type TransitionResult = { to: TaskState } | TransitionError

export interface TransitionContext {
  prevState?: TaskState | null
  origin?: TaskOrigin
  withinUndo?: boolean
  withinGrace?: boolean
  sameDay?: boolean
}

export function allowedActions(state: TaskState, origin: TaskOrigin = 'provider'): ActionName[] {
  const set = new Set(RULES[state] ?? [])
  if (state === 'snoozed' && origin !== 'user') set.delete('move')
  return ACTIONS.filter((a) => set.has(a))
}

export function transition(state: TaskState, action: string, ctx: TransitionContext = {}): TransitionResult {
  const { prevState = null, origin = 'provider', withinUndo = true, withinGrace = true, sameDay = true } = ctx
  const invalid = (allowed = allowedActions(state, origin)): TransitionError => ({
    error: 'invalid_transition',
    allowed,
  })
  if (!(ACTIONS as readonly string[]).includes(action)) return invalid()

  if (action === 'undo') {
    if (state !== 'done') return invalid()
    if (!withinUndo || (prevState !== 'suggested' && prevState !== 'accepted')) return { error: 'undo_expired' }
    return { to: prevState }
  }

  const target = TARGET[action] as TaskState
  if (state === target) return { to: state }
  if (state === 'done' && (action === 'complete_manual' || action === 'complete_event')) return { to: state }

  if (!(allowedActions(state, origin) as string[]).includes(action)) return invalid()
  if (state === 'expired' && !withinGrace) return invalid([])
  if (action === 'restore' && !sameDay) return invalid(allowedActions(state, origin).filter((a) => a !== 'restore'))
  return { to: target }
}

/** Cross-device rule (ERD 3.5): a completion always wins; against done only an undo applies; otherwise the later client time wins. */
export function incomingWins(currentState: TaskState, action: string, currentTs: number, clientTs: number): boolean {
  if (action === 'complete_manual' || action === 'complete_event') return true
  if (currentState === 'done') return action === 'undo'
  return clientTs >= currentTs
}
