import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

import { describe, expect, it } from 'vitest'

import {
  bulletList,
  cycleHeading,
  insertFormula,
  insertImage,
  insertTable,
  numberedList,
  taskList,
  toggleInline,
} from './edit-actions'
import { attachmentRefs, errorsOf, imagesMissingAlt, lint } from './lint'
import type { RichTextProfile } from './profiles'
import { charCount, plainText, sanitise } from './text'

const at = (value: string, start = 0, end = start) => ({ value, start, end })

describe('toggleInline', () => {
  it('wraps the selection and keeps it selected', () => {
    expect(toggleInline(at('a word b', 2, 6), '**', 'x')).toEqual({ value: 'a **word** b', start: 4, end: 8 })
  })

  it('unwraps when the markers are already there', () => {
    expect(toggleInline(at('a **word** b', 4, 8), '**', 'x')).toEqual({ value: 'a word b', start: 2, end: 6 })
  })

  it('inserts a placeholder with nothing selected', () => {
    expect(toggleInline(at('', 0), '*', 'italic text')).toEqual({ value: '*italic text*', start: 1, end: 12 })
  })
})

describe('line prefixes', () => {
  it('makes every selected line a bullet, and removes them again', () => {
    const on = bulletList(at('one\ntwo', 0, 7))
    expect(on.value).toBe('- one\n- two')
    expect(bulletList(at(on.value, on.start, on.end)).value).toBe('one\ntwo')
  })

  it('numbers lines from one', () => {
    expect(numberedList(at('a\nb\nc', 0, 5)).value).toBe('1. a\n2. b\n3. c')
  })

  it('turns a bullet into a task without double prefixes', () => {
    expect(taskList(at('- one', 0, 5)).value).toBe('- [ ] one')
    expect(bulletList(at('- [ ] one', 0, 9)).value).toBe('- one')
  })

  it('only touches the lines the selection covers', () => {
    expect(bulletList(at('keep\nthis\nnot', 5, 9)).value).toBe('keep\n- this\nnot')
  })
})

describe('cycleHeading', () => {
  it('goes none, 2, 3, 4, none on the current line', () => {
    let e = at('Title', 2)
    const seen: string[] = []
    for (let i = 0; i < 4; i++) {
      e = cycleHeading(e)
      seen.push(e.value)
    }
    expect(seen).toEqual(['## Title', '### Title', '#### Title', 'Title'])
  })
})

describe('blocks', () => {
  it('puts a table on its own lines and selects the first header', () => {
    const e = insertTable(at('intro', 5), 1, 2)
    expect(e.value).toBe('intro\n\n| Column 1 | Column 2 |\n| --- | --- |\n|   |   |\n')
    expect(e.value.slice(e.start, e.end)).toBe('Column 1')
  })

  it('inserts an inline formula around the selection, or a placeholder', () => {
    expect(insertFormula(at('x', 0, 1))).toEqual({ value: '$x$', start: 1, end: 2 })
    const empty = insertFormula(at('', 0))
    expect(empty.value).toBe('$x^2$')
    expect(empty.value.slice(empty.start, empty.end)).toBe('x^2')
  })

  it('inserts a display formula as its own block', () => {
    const e = insertFormula(at('a', 1), true)
    expect(e.value).toBe('a\n\n$$\n\\frac{a}{b}\n$$\n')
    expect(e.value.slice(e.start, e.end)).toBe('\\frac{a}{b}')
  })

  it('inserts an attachment image and strips brackets from the alt text', () => {
    const e = insertImage(at('see ', 4), 'id-1', 'Chart [2026]')
    expect(e.value).toBe('see ![Chart 2026](attachment:id-1)')
    expect(e.start).toBe(e.value.length)
  })
})

const ID = '123e4567-e89b-12d3-a456-426614174000'

describe('lint (note profile)', () => {
  it('reports the line of a problem and keeps warnings apart from errors', () => {
    const issues = lint('fine\n\n[x](javascript:alert(1))\n![](attachment:' + ID + ')', 'note')
    expect(issues.map((i) => [i.code, i.line, i.severity])).toEqual([
      ['link_scheme', 3, 'error'],
      ['missing_alt', 4, 'warning'],
    ])
    expect(errorsOf(issues)).toHaveLength(1)
  })

  it('counts code points, not UTF-16 units', () => {
    expect(charCount('😀'.repeat(3))).toBe(3)
    expect(lint('😀'.repeat(100_000), 'note')).toEqual([])
  })
})

describe('images', () => {
  it('lists uploaded images with their line and finds the ones without alt text', () => {
    const md = `a\n![](attachment:${ID})\n![Chart](attachment:${ID})\n\n\`\`\`\n![x](attachment:${ID})\n\`\`\``
    expect(attachmentRefs(md).map((i) => [i.alt, i.line])).toEqual([
      ['', 2],
      ['Chart', 3],
    ])
    expect(imagesMissingAlt(md)).toHaveLength(1)
  })
})

describe('sanitise', () => {
  it('is idempotent and keeps the Devanagari joiners', () => {
    const once = sanitise('a\r\nb \u202e c\u0000 क्\u200dष')
    expect(sanitise(once)).toBe(once)
    expect(once).toContain('क्\u200dष')
  })
})

interface Case {
  id: string
  profile: RichTextProfile
  markdown?: string
  repeat?: { unit: string; times: number }
  errors: string[]
  warnings: string[]
  text?: string
  sanitised?: string
}

// The server owns this corpus (`core/richtext.py` runs it too). Both linters pass the same file, so they cannot drift.
const SERVER_CORPUS = fileURLToPath(new URL('../../../../api/core/tests/richtext_cases.json', import.meta.url))
const corpus = JSON.parse(readFileSync(SERVER_CORPUS, 'utf8')) as { version: number; cases: Case[] }
const bodyOf = (c: Case) => (c.repeat ? c.repeat.unit.repeat(c.repeat.times) : (c.markdown ?? ''))
const codes = (c: Case, severity: 'error' | 'warning') =>
  [
    ...new Set(
      lint(bodyOf(c), c.profile)
        .filter((i) => i.severity === severity)
        .map((i) => i.code),
    ),
  ].sort()

describe('conformance with the server corpus', () => {
  it('is the version this twin was written for', () => {
    expect(corpus.version).toBe(1)
    expect(corpus.cases.length).toBeGreaterThanOrEqual(60)
  })

  it.each(corpus.cases.map((c) => [c.id, c] as const))('%s', (_id, c) => {
    expect(codes(c, 'error')).toEqual(c.errors)
    expect(codes(c, 'warning')).toEqual(c.warnings)
    if (c.text !== undefined) expect(plainText(bodyOf(c))).toBe(c.text)
    if (c.sanitised !== undefined) expect(sanitise(bodyOf(c))).toBe(c.sanitised)
  })
})
