/**
 * The pen's input rules as a pure state machine (FR-F03-23): which pointers draw, which scroll and which are a resting
 * palm. The capture surface feeds it one sample per pointer event and acts on what comes back; nothing here touches the
 * DOM, so every rule is tested with simulated pointer sequences.
 *
 *  - A stylus (`pen`) and a mouse draw. A pen taking over cancels a finger stroke in progress.
 *  - A finger scrolls the page unless "finger draws" is on. With it on, one finger draws and two fingers scroll.
 *  - Palm rejection: a touch is ignored while a pen is down, within `PALM_GUARD_MS` of the pen lifting or hovering, and when
 *    its contact patch is large (`PALM_CONTACT_PX`).
 */
export type PointerKind = 'pen' | 'touch' | 'mouse'

export interface PointerSample {
  /** `hover` is a pen moving above the glass: it only marks the pen as near, for palm rejection. */
  phase: 'down' | 'move' | 'up' | 'cancel' | 'hover'
  id: number
  kind: PointerKind
  x: number
  y: number
  /** Milliseconds (the event's `timeStamp`). */
  t: number
  /** Larger side of the contact patch in CSS pixels, when the device reports one. */
  contact?: number
}

export interface PenSettings {
  fingerDraws: boolean
}

export const PALM_CONTACT_PX = 40
export const PALM_GUARD_MS = 600

interface Pos {
  x: number
  y: number
}

export interface PenState {
  drawing: { id: number; kind: PointerKind } | null
  /** Fingers that are down and count (not palms). */
  touches: Record<number, Pos>
  /** Last time the pen touched or hovered, or -Infinity. */
  lastPenAt: number
  penDown: boolean
  ignored: number[]
}

export const initialPenState = (): PenState => ({
  drawing: null,
  touches: {},
  lastPenAt: Number.NEGATIVE_INFINITY,
  penDown: false,
  ignored: [],
})

export type PenEffect =
  | { type: 'begin'; id: number; kind: PointerKind; x: number; y: number; t: number }
  | { type: 'point'; x: number; y: number; t: number }
  /** The stroke is finished and kept. */
  | { type: 'end'; t: number }
  /** The stroke is dropped (a pen took over, a second finger came down, the browser took the gesture). */
  | { type: 'discard' }
  /** Two fingers moved: scroll the page by this much (the page follows the fingers). */
  | { type: 'scroll'; dx: number; dy: number }

/**
 * What the surface does with the pointer: `draw` means it is ours (capture it, prevent the default), `ignore` means
 * swallow it (a palm), `pass` means leave it to the browser (a finger that scrolls).
 */
export type PenClaim = 'draw' | 'ignore' | 'pass'

export interface PenStep {
  state: PenState
  effects: PenEffect[]
  claim: PenClaim
}

const midpoint = (touches: Record<number, Pos>): Pos | null => {
  const all = Object.values(touches)
  if (all.length < 2) return null
  return { x: all.reduce((n, p) => n + p.x, 0) / all.length, y: all.reduce((n, p) => n + p.y, 0) / all.length }
}

const isPalm = (s: PenState, sample: PointerSample) =>
  s.penDown || sample.t - s.lastPenAt < PALM_GUARD_MS || (sample.contact ?? 0) >= PALM_CONTACT_PX

export function stepPen(prev: PenState, sample: PointerSample, settings: PenSettings): PenStep {
  const state: PenState = { ...prev, touches: { ...prev.touches }, ignored: [...prev.ignored] }
  const effects: PenEffect[] = []
  const { id, kind, x, y, t } = sample

  if (kind === 'pen') {
    if (sample.phase === 'hover') state.lastPenAt = t
    if (sample.phase === 'down') {
      state.penDown = true
      state.lastPenAt = t
    }
    if (sample.phase === 'up' || sample.phase === 'cancel') {
      state.penDown = false
      state.lastPenAt = t
    }
  }

  if (sample.phase === 'hover') return { state, effects, claim: 'pass' }

  if (sample.phase === 'down') {
    if (kind === 'touch' && !settings.fingerDraws) return { state, effects, claim: 'pass' }
    if (kind === 'touch' && isPalm(prev, sample)) {
      state.ignored.push(id)
      return { state, effects, claim: 'ignore' }
    }
    if (kind === 'touch') {
      state.touches[id] = { x, y }
      if (Object.keys(state.touches).length >= 2) {
        // A second finger: this is a scroll or a pinch, not a stroke.
        if (state.drawing?.kind === 'touch') {
          effects.push({ type: 'discard' })
          state.drawing = null
        }
        return { state, effects, claim: 'ignore' }
      }
    }
    if (state.drawing) {
      // A pen taking over from a finger drops the finger stroke; any other overlap keeps the first stroke.
      if (kind === 'pen' && state.drawing.kind !== 'pen') effects.push({ type: 'discard' })
      else if (kind === 'pen') effects.push({ type: 'end', t })
      else return { state, effects, claim: 'ignore' }
    }
    state.drawing = { id, kind }
    effects.push({ type: 'begin', id, kind, x, y, t })
    return { state, effects, claim: 'draw' }
  }

  if (sample.phase === 'move') {
    if (state.ignored.includes(id)) return { state, effects, claim: 'ignore' }
    if (kind === 'touch' && id in state.touches) {
      const before = midpoint(prev.touches)
      state.touches[id] = { x, y }
      const after = midpoint(state.touches)
      if (before && after) {
        effects.push({ type: 'scroll', dx: before.x - after.x, dy: before.y - after.y })
        return { state, effects, claim: 'ignore' }
      }
    }
    if (state.drawing?.id === id) {
      effects.push({ type: 'point', x, y, t })
      return { state, effects, claim: 'draw' }
    }
    return { state, effects, claim: kind === 'touch' && !settings.fingerDraws ? 'pass' : 'ignore' }
  }

  // up or cancel
  const wasIgnored = state.ignored.includes(id)
  state.ignored = state.ignored.filter((i) => i !== id)
  delete state.touches[id]
  if (state.drawing?.id === id) {
    effects.push(sample.phase === 'cancel' ? { type: 'discard' } : { type: 'end', t })
    state.drawing = null
    return { state, effects, claim: 'draw' }
  }
  return { state, effects, claim: wasIgnored || kind !== 'touch' || settings.fingerDraws ? 'ignore' : 'pass' }
}
