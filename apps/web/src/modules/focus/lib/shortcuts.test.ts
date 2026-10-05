import { describe, expect, it } from 'vitest'

import { shortcutFor } from './shortcuts'

const open = { dialogOpen: false }

describe('shortcutFor', () => {
  it('maps Space, S and E', () => {
    expect(shortcutFor({ key: ' ', target: { tagName: 'BODY' } }, open)).toBe('toggle')
    expect(shortcutFor({ key: 's', target: { tagName: 'BODY' } }, open)).toBe('skip')
    expect(shortcutFor({ key: 'E', target: { tagName: 'DIV' } }, open)).toBe('end')
  })

  it('leaves typing alone', () => {
    for (const tagName of ['INPUT', 'TEXTAREA', 'SELECT'])
      expect(shortcutFor({ key: ' ', target: { tagName } }, open)).toBeNull()
    expect(shortcutFor({ key: 'e', target: { tagName: 'DIV', isContentEditable: true } }, open)).toBeNull()
  })

  it('does not steal Space from a focused button', () => {
    expect(shortcutFor({ key: ' ', target: { tagName: 'BUTTON' } }, open)).toBeNull()
  })

  it('ignores modified keys, other keys and open dialogs', () => {
    expect(shortcutFor({ key: 's', metaKey: true, target: null }, open)).toBeNull()
    expect(shortcutFor({ key: 'x', target: null }, open)).toBeNull()
    expect(shortcutFor({ key: ' ', target: null }, { dialogOpen: true })).toBeNull()
  })
})
