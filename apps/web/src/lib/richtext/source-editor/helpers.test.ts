import { describe, expect, it } from 'vitest'

import { minimalChange } from './diff'
import { createTabPolicy, isListLine } from './tab-policy'

describe('minimalChange', () => {
  it('returns null for equal text', () => expect(minimalChange('abc', 'abc')).toBeNull())

  it('finds the one span that changed', () => {
    expect(minimalChange('one two three', 'one 2 three')).toEqual({ from: 4, to: 7, insert: '2' })
    expect(minimalChange('', '1. ')).toEqual({ from: 0, to: 0, insert: '1. ' })
    expect(minimalChange('abc', '')).toEqual({ from: 0, to: 3, insert: '' })
  })

  it('applies back to the same text', () => {
    const cases: Array<[string, string]> = [
      ['aaa', 'aaaa'],
      ['- a\n- b', '1. a\n2. b'],
      ['x', 'xyx'],
    ]
    for (const [prev, next] of cases) {
      const c = minimalChange(prev, next)!
      expect(prev.slice(0, c.from) + c.insert + prev.slice(c.to)).toBe(next)
    }
  })

  it('never splits an emoji', () => {
    const c = minimalChange('a😀b', 'a😁b')!
    expect('a😀b'.slice(0, c.from) + c.insert + 'a😀b'.slice(c.to)).toBe('a😁b')
    expect(c).toEqual({ from: 1, to: 3, insert: '😁' })
  })
})

describe('tab policy', () => {
  it('knows list lines', () => {
    for (const line of ['- a', '* a', '+ a', '1. a', '12) a', '  - nested', '- [ ] task'])
      expect(isListLine(line)).toBe(true)
    for (const line of ['plain', '#heading', '1.5 is a number', '-dash', '']) expect(isListLine(line)).toBe(false)
  })

  it('indents inside a list and lets Tab through elsewhere', () => {
    const tabs = createTabPolicy()
    expect(tabs.shouldIndent('1. a', false)).toBe(true)
    expect(tabs.shouldIndent('plain', false)).toBe(false)
    expect(tabs.shouldIndent('   - a', true)).toBe(true)
    expect(tabs.shouldIndent('- a', true)).toBe(false)
  })

  it('Escape hands the next Tab back to the browser, once (no keyboard trap)', () => {
    const tabs = createTabPolicy()
    tabs.release()
    expect(tabs.shouldIndent('1. a', false)).toBe(false)
    expect(tabs.shouldIndent('1. a', false)).toBe(true)
  })

  it('typing again cancels the release', () => {
    const tabs = createTabPolicy()
    tabs.release()
    tabs.reset()
    expect(tabs.shouldIndent('1. a', false)).toBe(true)
  })
})
