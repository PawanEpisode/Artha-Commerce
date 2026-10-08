import { describe, expect, it } from 'vitest'

import { clozeIssues, clozeNumbers } from './cloze'
import { KINDS, SPECS, validate } from './kinds'
import { ordinals, render } from './render'

const codes = (kind: string, fields: Record<string, unknown>): Set<string> =>
  new Set(validate(kind, fields).map((i) => i.code))

describe('card kinds', () => {
  it('has a spec for every kind and renders a sample of each', () => {
    expect(Object.keys(SPECS).sort()).toEqual([...KINDS].sort())
    const samples: Record<string, Record<string, string>> = {
      pointer: { prompt_md: 'Q', answer_md: 'A' },
      formula: { name: 'Area', expression_md: '$a b$', when_md: 'rectangles' },
      section: { act: 'IT Act', reference: 's 80C', prompt_md: 'Limit?', gist_md: '1.5 lakh' },
      definition: { term: 'Asset', definition_md: 'A resource', source_ref: 'AS 1' },
      mnemonic: { mnemonic: 'FIFO', expands_md: 'First in first out' },
      case_law: { case_name: 'A v B', held_md: 'Held X', citation: '2020 SC 1', year: '2020' },
      cloze: { text_md: '{{c1::Cash}} is {{c2::king::hint}}' },
    }
    for (const [kind, fields] of Object.entries(samples)) {
      expect(validate(kind, fields)).toEqual([])
      const [front, back] = render(kind, fields, kind === 'cloze' ? 1 : 0)
      expect(front).not.toBe('')
      expect(back).not.toBe('')
    }
  })

  it('checks required fields, length, single line, unknown and non-text', () => {
    expect(codes('pointer', { prompt_md: ' ', answer_md: 'A' })).toContain('required')
    expect(codes('pointer', { prompt_md: 'x'.repeat(4001), answer_md: 'A' })).toContain('too_long')
    expect(codes('definition', { term: 'x'.repeat(201), definition_md: 'd' })).toContain('too_long')
    expect(codes('definition', { term: 'a\nb', definition_md: 'd' })).toContain('single_line')
    expect(codes('pointer', { prompt_md: 'Q', answer_md: 'A', x: '1' })).toContain('unknown_field')
    expect(codes('pointer', { prompt_md: 3, answer_md: 'A' })).toContain('not_text')
    expect([...codes('nope', {})]).toEqual(['unknown_kind'])
  })

  it.each([
    ['no deletion', 'cloze_none'],
    ['{{c1::a}} {{c1::b}}', 'cloze_duplicate'],
    ['{{c1::a}} {{c3::b}}', 'cloze_gap'],
    [Array.from({ length: 21 }, (_, i) => `{{c${i + 1}::x}}`).join(' '), 'cloze_too_many'],
  ])('cloze rule %#', (text, code) => {
    expect(clozeIssues(text).map((i) => i.code)).toEqual([code])
  })

  it('cloze faces hide only their own deletion', () => {
    const fields = { text_md: '{{c1::Cash}} is {{c2::king::hint}}' }
    expect(clozeNumbers(fields.text_md)).toEqual([1, 2])
    expect(ordinals('cloze', fields)).toEqual([1, 2])
    expect(ordinals('pointer', {})).toEqual([0])
    expect(render('cloze', fields, 1)).toEqual(['[...] is king', '**Cash** is king'])
    expect(render('cloze', fields, 2)).toEqual(['Cash is [hint]', 'Cash is **king**'])
  })
})
