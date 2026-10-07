import { describe, expect, it } from 'vitest'

import { markMiniNoteSeen, miniLayout, miniNoteSeen } from './mini-window'

describe('miniLayout', () => {
  it('is the pill below 300 px wide and the card above, when the window is tall enough for the ring', () => {
    expect(miniLayout(299, 400)).toBe('pill')
    expect(miniLayout(300, 400)).toBe('card')
    expect(miniLayout(320, 300)).toBe('card')
  })

  it('stays the pill in the default 320 x 220 window, where the ring would not fit', () => {
    expect(miniLayout(320, 220)).toBe('pill')
    expect(miniLayout(0, 0)).toBe('pill')
  })
})

describe('the one-time note', () => {
  it('is remembered once marked', () => {
    const data = new Map<string, string>()
    const store = {
      getItem: (k: string) => data.get(k) ?? null,
      setItem: (k: string, v: string) => void data.set(k, v),
    }
    expect(miniNoteSeen(store)).toBe(false)
    markMiniNoteSeen(store)
    expect(miniNoteSeen(store)).toBe(true)
  })

  it('shows again, without failing, where storage throws', () => {
    const broken = {
      getItem: () => {
        throw new Error('blocked')
      },
      setItem: () => {
        throw new Error('blocked')
      },
    }
    expect(miniNoteSeen(broken)).toBe(false)
    expect(() => markMiniNoteSeen(broken)).not.toThrow()
  })
})
