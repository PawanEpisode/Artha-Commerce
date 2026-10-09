/**
 * What the card form shows for the seven kinds: names, field labels and hints. The rules (`validate`) and the preview
 * text (`render`) are the W2 twins of the server, not copied here; this file only puts a student's words on them.
 */

import { clozeNumbers } from './cloze'
import { type CardKind, KINDS, SPECS, validate } from './kinds'
import { FIELD_MAX_CHARS, MAX_TAG_CHARS, MAX_TAGS, SHORT_FIELD_MAX_CHARS } from './limits'

export { FIELD_MAX_CHARS, MAX_TAG_CHARS, MAX_TAGS, SHORT_FIELD_MAX_CHARS }
export { KINDS as CARD_KINDS, type CardKind }
export { ordinals as facesOf, render as renderFace } from './render'

export type Fields = Record<string, string>
export interface FieldIssue {
  field: string
  code: string
  message: string
}

export const isCardKind = (v: unknown): v is CardKind => (KINDS as readonly string[]).includes(v as string)

export const KIND_LABELS: Record<CardKind, { label: string; blurb: string }> = {
  pointer: { label: 'Question and answer', blurb: 'A plain prompt and its answer.' },
  formula: { label: 'Formula', blurb: 'A name, the expression and when to use it.' },
  section: { label: 'Section', blurb: 'What a section of an Act says.' },
  definition: { label: 'Definition', blurb: 'A term and its meaning.' },
  mnemonic: { label: 'Mnemonic', blurb: 'A memory aid and what it stands for.' },
  case_law: { label: 'Case law', blurb: 'A case, its facts and what was held.' },
  cloze: { label: 'Fill in the blank', blurb: 'A sentence with hidden words.' },
}

export const FIELD_TEXT: Record<string, { label: string; hint?: string }> = {
  prompt_md: { label: 'Question' },
  answer_md: { label: 'Answer' },
  name: { label: 'Name' },
  expression_md: { label: 'Formula', hint: 'Use $...$ for maths.' },
  variables_md: { label: 'What the letters mean' },
  when_md: { label: 'When to use it' },
  act: { label: 'Act' },
  reference: { label: 'Section', hint: 'For example: Section 80C' },
  gist_md: { label: 'In short' },
  exceptions_md: { label: 'Exceptions' },
  term: { label: 'Term' },
  definition_md: { label: 'Meaning' },
  source_ref: { label: 'Source' },
  mnemonic: { label: 'Mnemonic' },
  expands_md: { label: 'What it stands for' },
  topic: { label: 'Topic' },
  case_name: { label: 'Case name' },
  citation: { label: 'Citation' },
  court: { label: 'Court' },
  year: { label: 'Year' },
  facts_md: { label: 'Facts' },
  held_md: { label: 'What was held' },
  text_md: {
    label: 'Text',
    hint: 'Hide a word like {{c1::this}}. Add a hint with {{c1::this::a hint}}. Number the blanks 1, 2, 3.',
  },
}

export interface FormField {
  name: string
  label: string
  hint?: string
  required: boolean
  short: boolean
  max: number
}

export const formFields = (kind: CardKind): FormField[] =>
  SPECS[kind].map((s) => ({
    name: s.name,
    label: FIELD_TEXT[s.name]?.label ?? s.name,
    hint: FIELD_TEXT[s.name]?.hint,
    required: s.required,
    short: s.short,
    max: s.short ? SHORT_FIELD_MAX_CHARS : FIELD_MAX_CHARS,
  }))

const sentence = (field: string, code: string, fallback: string, label: string, max: number): string => {
  switch (code) {
    case 'required':
      return `${label} is needed.`
    case 'too_long':
      return `${label} is longer than ${max} characters.`
    case 'single_line':
      return `${label} must be one line.`
    default:
      return field === 'text_md' ? fallback : `${label}: ${fallback}`
  }
}

/** Problems the form can show before a round trip, one sentence each. Empty means it can be sent. */
export function validateForm(kind: CardKind, fields: Fields): FieldIssue[] {
  const byName = new Map(formFields(kind).map((f) => [f.name, f]))
  return validate(kind, fields).map((i) => {
    const f = byName.get(i.field)
    return { ...i, message: sentence(i.field, i.code, i.message, f?.label ?? i.field, f?.max ?? FIELD_MAX_CHARS) }
  })
}

export function validateTags(tags: readonly string[]): string | null {
  if (tags.length > MAX_TAGS) return `At most ${MAX_TAGS} tags are allowed.`
  return tags.some((t) => [...t].length > MAX_TAG_CHARS) ? `A tag has at most ${MAX_TAG_CHARS} characters.` : null
}

/** Comma separated text to tags: trimmed, no blanks, no repeats. */
export const parseTags = (text: string): string[] => [
  ...new Set(
    text
      .split(',')
      .map((t) => t.trim())
      .filter(Boolean),
  ),
]

export const emptyFields = (kind: CardKind): Fields => Object.fromEntries(SPECS[kind].map((s) => [s.name, '']))

/** Only the fields of this kind, as text. Anything else the server sent is ignored. */
export const fieldsOf = (kind: CardKind, raw: Record<string, unknown>): Fields =>
  Object.fromEntries(SPECS[kind].map((s) => [s.name, typeof raw[s.name] === 'string' ? (raw[s.name] as string) : '']))

/** The field a pasted selection goes into for each kind: the long text the student would otherwise type first. */
const DRAFT_FIELD: Record<CardKind, string> = {
  pointer: 'prompt_md',
  formula: 'expression_md',
  section: 'gist_md',
  definition: 'definition_md',
  mnemonic: 'expands_md',
  case_law: 'facts_md',
  cloze: 'text_md',
}
export const withDraft = (kind: CardKind, draft: string): Fields => ({
  ...emptyFields(kind),
  [DRAFT_FIELD[kind]]: draft,
})

/** A guess at the kind for a passage by the server's simple rules. The student can always change it. */
export function suggestKind(text: string): CardKind {
  const t = text.trim()
  if (/\b[A-Z][\w.&'-]*(?:\s+[A-Z][\w.&'-]*)*\s+(?:v\.?|vs\.?)\s+[A-Z]/u.test(t)) return 'case_law'
  if (/\b(?:section|sec\.?|rule|article|regulation)\s+\d+/i.test(t)) return 'section'
  if (t.includes('=') || t.includes('\\frac') || t.includes('$')) return 'formula'
  if (/\b(?:means|is defined as|are defined as|shall mean|refers to)\b/i.test(t)) return 'definition'
  return 'pointer'
}

export const clozeCount = (text: string): number => clozeNumbers(text).length
