/** Card kinds and field forms: twin of the specs and `validate` in `domain/cards.py`. */

import { clozeIssues } from './cloze'
import { FIELD_MAX_CHARS, SHORT_FIELD_MAX_CHARS } from './limits'

export const KINDS = ['pointer', 'formula', 'section', 'definition', 'mnemonic', 'case_law', 'cloze'] as const
export type CardKind = (typeof KINDS)[number]

export interface FieldSpec {
  name: string
  required: boolean
  /** Plain one-line field of at most 200 characters; the others are Markdown up to 4,000. */
  short: boolean
}

const f = (name: string, required = true, short = false): FieldSpec => ({ name, required, short })

export const SPECS: Record<CardKind, readonly FieldSpec[]> = {
  pointer: [f('prompt_md'), f('answer_md')],
  formula: [f('name', true, true), f('expression_md'), f('variables_md', false), f('when_md', false)],
  section: [f('act', false, true), f('reference', true, true), f('prompt_md'), f('gist_md'), f('exceptions_md', false)],
  definition: [f('term', true, true), f('definition_md'), f('source_ref', false, true)],
  mnemonic: [f('mnemonic', true, true), f('expands_md'), f('topic', false, true)],
  case_law: [
    f('case_name', true, true),
    f('citation', false, true),
    f('court', false, true),
    f('year', false, true),
    f('facts_md', false),
    f('held_md'),
  ],
  cloze: [f('text_md')],
}

export interface Issue {
  field: string
  code: string
  message: string
}

export function validate(kind: string, fields: Readonly<Record<string, unknown>>): Issue[] {
  if (!(kind in SPECS))
    return [{ field: 'kind', code: 'unknown_kind', message: `Unknown card kind ${JSON.stringify(kind)}.` }]
  const specs = SPECS[kind as CardKind]
  const issues: Issue[] = []
  const names = new Set(specs.map((s) => s.name))
  for (const name of Object.keys(fields)) {
    if (!names.has(name) && name !== 'v')
      issues.push({ field: name, code: 'unknown_field', message: `${name} is not a field of a ${kind} card.` })
  }
  for (const spec of specs) {
    let raw = fields[spec.name]
    if (raw === undefined || raw === null) raw = ''
    if (typeof raw !== 'string') {
      issues.push({ field: spec.name, code: 'not_text', message: `${spec.name} must be text.` })
      continue
    }
    const value = raw.trim()
    const limit = spec.short ? SHORT_FIELD_MAX_CHARS : FIELD_MAX_CHARS
    if (spec.required && value === '')
      issues.push({ field: spec.name, code: 'required', message: `${spec.name} is required.` })
    else if ([...value].length > limit)
      issues.push({ field: spec.name, code: 'too_long', message: `${spec.name} is longer than ${limit} characters.` })
    else if (spec.short && value.includes('\n'))
      issues.push({ field: spec.name, code: 'single_line', message: `${spec.name} must be one line.` })
  }
  if (kind === 'cloze' && typeof fields.text_md === 'string') {
    for (const i of clozeIssues(fields.text_md)) issues.push({ field: 'text_md', code: i.code, message: i.message })
  }
  return issues
}
