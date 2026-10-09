import { describe, expect, it } from 'vitest'

import { ApiError } from '~/lib/api'

import { mergeFields, resolve } from './cardConflict'
import { cardFailure } from './cardErrors'
import {
  CARD_KINDS,
  type CardKind,
  emptyFields,
  type Fields,
  fieldsOf,
  parseTags,
  suggestKind,
  validateForm,
  validateTags,
  withDraft,
} from './cardKinds'
import { cardsSearchSchema, hasFilters, listParams, newCardSearchSchema } from './cardSearch'

const GOOD: Record<CardKind, Fields> = {
  pointer: { prompt_md: 'What is GST?', answer_md: 'A tax on supply.' },
  formula: { name: 'Simple interest', expression_md: '$P r t$' },
  section: { reference: 'Section 80C', prompt_md: 'Limit?', gist_md: 'Rs 1.5 lakh' },
  definition: { term: 'Assessee', definition_md: 'A person who pays tax.' },
  mnemonic: { mnemonic: 'VIBGYOR', expands_md: 'Colours of the rainbow' },
  case_law: { case_name: 'A v B', held_md: 'It was held.' },
  cloze: { text_md: 'The capital of India is {{c1::Delhi}}.' },
}

describe('card form validation, one block per kind', () => {
  it.each(CARD_KINDS)('%s: a complete form is valid and an empty one names what is missing', (kind) => {
    expect(validateForm(kind, { ...emptyFields(kind), ...GOOD[kind] })).toEqual([])
    const empty = validateForm(kind, emptyFields(kind))
    expect(empty.length).toBeGreaterThan(0)
    for (const issue of empty) expect(issue.message).not.toMatch(/_md|_ref|is required/)
  })

  it('says each missing field in a student’s words', () => {
    expect(validateForm('pointer', { prompt_md: '', answer_md: 'x' }).map((i) => i.message)).toEqual([
      'Question is needed.',
    ])
    expect(validateForm('case_law', { case_name: 'A v B', held_md: '' }).map((i) => i.message)).toEqual([
      'What was held is needed.',
    ])
  })

  it('counts a short field against 200 and a long one against 4,000, and refuses a line break in a short one', () => {
    const long = validateForm('definition', { term: 'x'.repeat(201), definition_md: 'ok' })
    expect(long).toHaveLength(1)
    expect(long[0]).toMatchObject({ field: 'term', code: 'too_long', message: 'Term is longer than 200 characters.' })
    expect(validateForm('pointer', { prompt_md: 'q', answer_md: 'x'.repeat(4001) })[0]?.code).toBe('too_long')
    expect(validateForm('pointer', { prompt_md: 'q', answer_md: 'x'.repeat(4000) })).toEqual([])
    expect(validateForm('definition', { term: 'a\nb', definition_md: 'ok' })[0]?.message).toBe('Term must be one line.')
  })

  it('checks the blanks of a fill in the blank card', () => {
    const msg = (text_md: string) => validateForm('cloze', { text_md }).map((i) => i.code)
    expect(msg('No blanks here')).toEqual(['cloze_none'])
    expect(msg('{{c1::a}} and {{c1::b}}')).toEqual(['cloze_duplicate'])
    expect(msg('{{c1::a}} and {{c3::b}}')).toEqual(['cloze_gap'])
    expect(msg('{{c1::a}} and {{c2::b::hint}}')).toEqual([])
  })

  it('limits tags', () => {
    expect(validateTags(['a', 'b'])).toBeNull()
    expect(validateTags(Array.from({ length: 13 }, (_, i) => `t${i}`))).toMatch(/At most 12/)
    expect(validateTags(['x'.repeat(41)])).toMatch(/at most 40/)
    expect(parseTags(' a, b ,,a, c ')).toEqual(['a', 'b', 'c'])
  })
})

describe('prefill and kind suggestion', () => {
  it('puts a selection into the long field of the kind', () => {
    expect(withDraft('pointer', 'Some text').prompt_md).toBe('Some text')
    expect(withDraft('cloze', 'Some text').text_md).toBe('Some text')
    expect(withDraft('case_law', 'x').facts_md).toBe('x')
  })

  it('suggests a kind from the text, and falls back to a plain question', () => {
    expect(suggestKind('Kesavananda v. State of Kerala, Supreme Court held')).toBe('case_law')
    expect(suggestKind('Section 80C allows a deduction')).toBe('section')
    expect(suggestKind('E = mc^2')).toBe('formula')
    expect(suggestKind('An assessee means any person')).toBe('definition')
    expect(suggestKind('Some ordinary sentence.')).toBe('pointer')
  })

  it('keeps only the fields of the kind, as text', () => {
    expect(fieldsOf('pointer', { prompt_md: 'q', answer_md: 5, extra: 'x' })).toEqual({ prompt_md: 'q', answer_md: '' })
  })
})

describe('three way merge of an edit', () => {
  const base = { prompt_md: 'Q', answer_md: 'A' }

  it('keeps a change only one side made, and flags what both changed differently', () => {
    const m = mergeFields(base, { prompt_md: 'Q mine', answer_md: 'A' }, { prompt_md: 'Q', answer_md: 'A theirs' })
    expect(m.conflicts).toEqual([])
    expect(m.merged).toEqual({ prompt_md: 'Q mine', answer_md: 'A theirs' })
    const c = mergeFields(base, { prompt_md: 'mine', answer_md: 'A' }, { prompt_md: 'theirs', answer_md: 'A' })
    expect(c.conflicts).toEqual([{ field: 'prompt_md', base: 'Q', mine: 'mine', theirs: 'theirs' }])
    expect(resolve(c, { prompt_md: 'theirs' }).prompt_md).toBe('theirs')
    expect(resolve(c, { prompt_md: 'mine' }).prompt_md).toBe('mine')
  })

  it('is not a conflict when both made the same change', () => {
    expect(mergeFields(base, { prompt_md: 'Z', answer_md: 'A' }, { prompt_md: 'Z', answer_md: 'A' }).conflicts).toEqual(
      [],
    )
  })
})

describe('what a failed card write means', () => {
  const api = (status: number, code: string, details?: unknown, message = 'm') =>
    new ApiError(status, 'x', { error: { code, message, details } })

  it('reads the server’s codes', () => {
    expect(cardFailure(api(409, 'duplicate_card', { card_id: 'c1' }))).toEqual({ kind: 'duplicate', cardId: 'c1' })
    expect(cardFailure(api(409, 'edit_conflict', { server_fields: { prompt_md: 'T' }, rev: 7 }))).toEqual({
      kind: 'conflict',
      serverFields: { prompt_md: 'T' },
      rev: 7,
    })
    expect(
      cardFailure(
        api(422, 'invalid_fields', { errors: [{ field: 'text_md', code: 'cloze_none', message: 'Add one.' }] }),
      ),
    ).toEqual({ kind: 'invalid', issues: [{ field: 'text_md', code: 'cloze_none', message: 'Add one.' }] })
    expect(cardFailure(api(429, 'quota_exceeded', undefined, 'Limit reached.'))).toEqual({
      kind: 'quota',
      message: 'Limit reached.',
    })
    expect(cardFailure(api(410, 'card_deleted'))).toEqual({ kind: 'deleted' })
    expect(cardFailure(api(429, 'throttled'))).toEqual({ kind: 'throttled' })
  })

  it('treats a failed fetch and a server error as a network problem', () => {
    expect(cardFailure(new TypeError('Failed to fetch'))).toEqual({ kind: 'network' })
    expect(cardFailure(api(503, 'unavailable'))).toEqual({ kind: 'network' })
  })
})

describe('URL filters', () => {
  it('reads filters from the URL and ignores values it does not know', () => {
    expect(
      cardsSearchSchema.parse({ kind: 'cloze', tier: 'mandatory', q: 'gst', state: 'tricky', sort: 'oldest' }),
    ).toMatchObject({
      kind: 'cloze',
      tier: 'mandatory',
      state: 'tricky',
      sort: 'oldest',
    })
    const bad = cardsSearchSchema.parse({ kind: 'nonsense', chapter: 'not-a-uuid', sort: 'sideways' })
    expect(bad).toEqual({})
    expect(hasFilters(bad)).toBe(false)
  })

  it('turns the URL into the API’s query names', () => {
    const s = cardsSearchSchema.parse({
      kind: 'formula',
      chapter: '11111111-1111-4111-8111-111111111111',
      q: ' tax ',
      sort: 'newest',
    })
    expect(listParams(s)).toEqual({
      q: 'tax',
      kind: 'formula',
      tier: undefined,
      state: undefined,
      chapter_id: '11111111-1111-4111-8111-111111111111',
      deck_id: undefined,
      sort: undefined,
    })
    expect(hasFilters(s)).toBe(true)
  })

  it('reads the creator’s prefill', () => {
    expect(newCardSearchSchema.parse({ kind: 'cloze', from: 'selection', draft: 'text' })).toMatchObject({
      kind: 'cloze',
      from: 'selection',
      draft: 'text',
    })
  })
})
