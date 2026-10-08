/**
 * Pure render of a card face to front and back Markdown: twin of `render` in `domain/cards.py`, so the offline pack and the
 * server show the same text. (The kind suggestion and the duplicate fingerprint stay on the server.)
 */

import { clozeNumbers, clozePattern } from './cloze'
import type { CardKind } from './kinds'

type Fields = Readonly<Record<string, unknown>>

const s = (fields: Fields, name: string): string => {
  const v = fields[name]
  return typeof v === 'string' ? v.trim() : ''
}
const join = (...parts: string[]): string => parts.filter((p) => p !== '').join('\n\n')

/** One card face per cloze number, else the single face 0. */
export function ordinals(kind: string, fields: Fields): number[] {
  return kind === 'cloze' ? clozeNumbers(String(fields.text_md ?? '')).sort((a, b) => a - b) : [0]
}

export function render(kind: CardKind | string, fields: Fields, ordinal = 0): [string, string] {
  switch (kind) {
    case 'pointer':
      return [s(fields, 'prompt_md'), s(fields, 'answer_md')]
    case 'formula': {
      const hint = s(fields, 'when_md')
      return [
        join(`**${s(fields, 'name')}**`, hint ? `When to use: ${hint}` : ''),
        join(s(fields, 'expression_md'), s(fields, 'variables_md')),
      ]
    }
    case 'section': {
      const head = [s(fields, 'act'), s(fields, 'reference')].filter((p) => p !== '').join(' ')
      const exceptions = s(fields, 'exceptions_md')
      return [
        join(`**${head}**`, s(fields, 'prompt_md')),
        join(s(fields, 'gist_md'), exceptions ? `**Exceptions**\n\n${exceptions}` : ''),
      ]
    }
    case 'definition': {
      const source = s(fields, 'source_ref')
      return [`**${s(fields, 'term')}**`, join(s(fields, 'definition_md'), source ? `Source: ${source}` : '')]
    }
    case 'mnemonic':
      return [
        join(s(fields, 'topic'), `**${s(fields, 'mnemonic')}**`, 'What does it stand for?'),
        s(fields, 'expands_md'),
      ]
    case 'case_law': {
      const cite = [s(fields, 'citation'), s(fields, 'court'), s(fields, 'year')].filter((p) => p !== '').join(', ')
      return [join(`**${s(fields, 'case_name')}**`, s(fields, 'facts_md')), join(s(fields, 'held_md'), cite)]
    }
    case 'cloze': {
      const text = s(fields, 'text_md')
      const front = text.replace(clozePattern(), (_m, n: string, answer: string, hint?: string) =>
        Number(n) === ordinal ? (hint ? `[${hint}]` : '[...]') : answer,
      )
      const back = text.replace(clozePattern(), (_m, n: string, answer: string) =>
        Number(n) === ordinal ? `**${answer}**` : answer,
      )
      return [front, back]
    }
    default:
      throw new Error(`Unknown card kind ${JSON.stringify(kind)}`)
  }
}
