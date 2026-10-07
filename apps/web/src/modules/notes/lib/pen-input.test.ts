import { describe, expect, it } from 'vitest'

import {
  initialPenState,
  PALM_CONTACT_PX,
  PALM_GUARD_MS,
  type PenEffect,
  type PenState,
  type PointerSample,
  stepPen,
} from './pen-input'

/** Feeds a pointer sequence through the state machine and collects every effect and claim. */
function run(samples: PointerSample[], fingerDraws = false) {
  let state: PenState = initialPenState()
  const effects: PenEffect[] = []
  const claims: string[] = []
  for (const sample of samples) {
    const step = stepPen(state, sample, { fingerDraws })
    state = step.state
    effects.push(...step.effects)
    claims.push(step.claim)
  }
  return { state, effects, claims }
}

const s = (
  phase: PointerSample['phase'],
  id: number,
  kind: PointerSample['kind'],
  x: number,
  y: number,
  t: number,
  contact?: number,
): PointerSample => ({
  phase,
  id,
  kind,
  x,
  y,
  t,
  contact,
})
const types = (effects: PenEffect[]) => effects.map((e) => e.type)

describe('stylus', () => {
  it('draws: begin, points, end, and claims the pointer', () => {
    const { effects, claims } = run([
      s('down', 1, 'pen', 10, 10, 0),
      s('move', 1, 'pen', 20, 20, 10),
      s('move', 1, 'pen', 30, 30, 20),
      s('up', 1, 'pen', 30, 30, 30),
    ])
    expect(types(effects)).toEqual(['begin', 'point', 'point', 'end'])
    expect(claims.every((c) => c === 'draw')).toBe(true)
  })

  it('treats a hover as passing, and only remembers that the pen is near', () => {
    const { effects, claims, state } = run([s('hover', 1, 'pen', 5, 5, 100)])
    expect(effects).toEqual([])
    expect(claims).toEqual(['pass'])
    expect(state.lastPenAt).toBe(100)
  })
})

describe('touch', () => {
  it('scrolls: a finger is left to the browser and draws nothing', () => {
    const { effects, claims } = run([
      s('down', 1, 'touch', 10, 10, 0),
      s('move', 1, 'touch', 10, 60, 16),
      s('up', 1, 'touch', 10, 60, 32),
    ])
    expect(effects).toEqual([])
    expect(claims).toEqual(['pass', 'pass', 'pass'])
  })

  it('draws with one finger when "finger draws" is on', () => {
    const { effects } = run(
      [s('down', 1, 'touch', 10, 10, 0), s('move', 1, 'touch', 20, 20, 16), s('up', 1, 'touch', 20, 20, 32)],
      true,
    )
    expect(types(effects)).toEqual(['begin', 'point', 'end'])
  })

  it('with "finger draws" on, a second finger drops the stroke and scrolls the page', () => {
    const { effects } = run(
      [
        s('down', 1, 'touch', 10, 10, 0),
        s('move', 1, 'touch', 12, 12, 8),
        s('down', 2, 'touch', 50, 10, 16),
        s('move', 2, 'touch', 50, 40, 24),
        s('up', 2, 'touch', 50, 40, 32),
        s('up', 1, 'touch', 12, 40, 40),
      ],
      true,
    )
    expect(types(effects)).toEqual(['begin', 'point', 'discard', 'scroll'])
    const scroll = effects.find((e) => e.type === 'scroll')
    expect(scroll).toMatchObject({ dx: 0 })
    expect((scroll as { dy: number }).dy).toBeLessThan(0)
  })
})

describe('palm rejection', () => {
  it('ignores a touch while the pen is down, and keeps drawing', () => {
    const { effects, claims } = run(
      [
        s('down', 1, 'pen', 10, 10, 0),
        s('down', 2, 'touch', 80, 80, 5),
        s('move', 2, 'touch', 82, 82, 10),
        s('move', 1, 'pen', 20, 20, 12),
        s('up', 2, 'touch', 82, 82, 14),
        s('up', 1, 'pen', 20, 20, 16),
      ],
      true,
    )
    expect(types(effects)).toEqual(['begin', 'point', 'end'])
    expect(claims.slice(1, 3)).toEqual(['ignore', 'ignore'])
  })

  it('ignores a touch just after the pen lifted, and accepts one after the guard time', () => {
    const early = run(
      [
        s('down', 1, 'pen', 0, 0, 0),
        s('up', 1, 'pen', 0, 0, 100),
        s('down', 2, 'touch', 5, 5, 100 + PALM_GUARD_MS - 1),
      ],
      true,
    )
    expect(early.claims[2]).toBe('ignore')
    const late = run(
      [
        s('down', 1, 'pen', 0, 0, 0),
        s('up', 1, 'pen', 0, 0, 100),
        s('down', 2, 'touch', 5, 5, 100 + PALM_GUARD_MS + 1),
      ],
      true,
    )
    expect(late.claims[2]).toBe('draw')
  })

  it('ignores a touch with a large contact patch', () => {
    const { effects, claims } = run(
      [s('down', 1, 'touch', 5, 5, 0, PALM_CONTACT_PX), s('move', 1, 'touch', 9, 9, 8, PALM_CONTACT_PX)],
      true,
    )
    expect(effects).toEqual([])
    expect(claims).toEqual(['ignore', 'ignore'])
  })

  it('a pen taking over drops a finger stroke in progress', () => {
    const { effects } = run(
      [s('down', 1, 'touch', 5, 5, 0), s('move', 1, 'touch', 9, 9, 8), s('down', 2, 'pen', 50, 50, 16)],
      true,
    )
    expect(types(effects)).toEqual(['begin', 'point', 'discard', 'begin'])
  })
})

describe('mouse and cancel', () => {
  it('draws with a mouse', () => {
    expect(
      types(
        run([s('down', 1, 'mouse', 1, 1, 0), s('move', 1, 'mouse', 5, 5, 4), s('up', 1, 'mouse', 5, 5, 8)]).effects,
      ),
    ).toEqual(['begin', 'point', 'end'])
  })

  it('discards a stroke the browser cancelled (for example it took the gesture to scroll)', () => {
    expect(types(run([s('down', 1, 'pen', 1, 1, 0), s('cancel', 1, 'pen', 1, 1, 4)]).effects)).toEqual([
      'begin',
      'discard',
    ])
  })
})
