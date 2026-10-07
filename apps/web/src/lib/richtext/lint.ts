/* eslint-disable @typescript-eslint/no-non-null-assertion -- regex groups and indexed access are guaranteed by the patterns above them */
/** The twin of `lint` in `apps/api/core/richtext.py`. Errors block a save, warnings are shown to the author. */

import { PROFILES, type RichTextProfile } from './profiles'
import { AUTOLINK, charCount, maskCode } from './text'

export type IssueSeverity = 'error' | 'warning'

export interface Issue {
  code: string
  message: string
  /** 1-based; undefined for whole-body issues. */
  line?: number
  severity: IssueSeverity
}

export interface ImageRef {
  attachmentId: string
  alt: string
  line: number
}

const DISPLAY_MATH = /\$\$(.+?)\$\$/gs
// Inline math follows the Pandoc rule so prices do not become formulas (same expression as the server).
const INLINE_MATH = /(?<![\\$])\$(?!\$)(?=\S)([^$\n]*?\S)(?<!\\)\$(?!\$)/g
const FORBIDDEN_TEX =
  /\\(href|url|includegraphics|html[A-Za-z]*|def|edef|gdef|xdef|newcommand|renewcommand|providecommand|input|write)(?![A-Za-z])/
const ATTACHMENT = /^attachment:([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})$/
const IMAGE = /!\[([^\]\n]*)\]\(\s*([^)\s]*)(?:\s+"[^"\n]*")?\s*\)/g
const LINK = /(?<!!)\[[^\]\n]*\]\(\s*([^)\s]*)(?:\s+"[^"\n]*")?\s*\)/g
const HTML_TAG = /<\/?[A-Za-z][^<>\n]*>|<!--/
const ATX = /^ {0,3}(#{1,6})(?:\s|$)/
const RULE = /^ {0,3}([-*_])(?: *\1){2,} *$/
const SETEXT = /^ {0,3}(=+|-+) *$/
const TASK = /^\s*(?:[-*+]|\d+[.)])\s+\[[ xX]\](?:\s|$)/
const FOOTNOTE = /\[\^[^\]\s]+\]/
const TABLE_DELIMITER = /^\s*\|?\s*:?-+:?\s*(\|\s*:?-+:?\s*)*\|?\s*$/

const lineAt = (text: string, pos: number) => text.slice(0, pos).split('\n').length

function cells(row: string): number {
  let r = row.trim()
  r = r.startsWith('|') ? r.slice(1) : r
  r = r.endsWith('|') && !r.endsWith('\\|') ? r.slice(0, -1) : r
  return r.split(/(?<!\\)\|/).length
}

function tableIssues(lines: string[], p: (typeof PROFILES)[RichTextProfile]): Issue[] {
  const issues: Issue[] = []
  let i = 0
  while (i < lines.length - 1) {
    const header = lines[i]!
    const delimiter = lines[i + 1]!
    if (
      header.includes('|') &&
      TABLE_DELIMITER.test(delimiter) &&
      delimiter.includes('-') &&
      (header + delimiter).includes('|')
    ) {
      const cols = cells(header)
      let rows = 0
      let j = i + 2
      while (j < lines.length && lines[j]!.trim() && lines[j]!.includes('|')) {
        rows += 1
        j += 1
      }
      if (cols > p.maxTableCols || rows > p.maxTableRows) {
        issues.push({
          code: 'table_too_large',
          message: `Tables can have at most ${p.maxTableRows} rows and ${p.maxTableCols} columns.`,
          line: i + 1,
          severity: 'error',
        })
      }
      i = j
    } else {
      i += 1
    }
  }
  return issues
}

function headingIssues(lines: string[], p: (typeof PROFILES)[RichTextProfile]): Issue[] {
  const issues: Issue[] = []
  lines.forEach((line, index) => {
    const n = index + 1
    let level: number | null = null
    const atx = ATX.exec(line)
    if (atx) {
      level = atx[1]!.length
    } else if (n > 1 && lines[n - 2]!.trim() && !ATX.test(lines[n - 2]!)) {
      const setext = SETEXT.exec(line)
      if (setext && !/^[-*+>|]/.test(lines[n - 2]!.trimStart())) level = setext[1]![0] === '=' ? 1 : 2
    }
    if (level === null) return
    if (p.headings === null || level < p.headings[0] || level > p.headings[1]) {
      const allowed = p.headings === null ? 'not allowed here' : `allowed from ${p.headings[0]} to ${p.headings[1]}`
      issues.push({ code: 'heading_level', message: `Headings are ${allowed}.`, line: n, severity: 'error' })
    }
  })
  return issues
}

function ruleIssues(lines: string[], p: (typeof PROFILES)[RichTextProfile]): Issue[] {
  if (p.rules) return []
  const issues: Issue[] = []
  lines.forEach((line, index) => {
    const previousBlank = index === 0 || !lines[index - 1]!.trim()
    if (RULE.test(line) && previousBlank) {
      issues.push({
        code: 'rule_not_allowed',
        message: 'Horizontal rules are not allowed here.',
        line: index + 1,
        severity: 'error',
      })
    }
  })
  return issues
}

function mathIssues(masked: string, p: (typeof PROFILES)[RichTextProfile]): Issue[] {
  const issues: Issue[] = []
  const expressions: Array<[string, number]> = []
  for (const m of masked.matchAll(DISPLAY_MATH)) expressions.push([m[1]!, lineAt(masked, m.index!)])
  const rest = masked.replace(DISPLAY_MATH, (m) => m.replace(/[^\n]/g, ' '))
  for (const m of rest.matchAll(INLINE_MATH)) expressions.push([m[1]!, lineAt(rest, m.index!)])
  if (expressions.length > p.maxMathCount) {
    issues.push({
      code: 'too_many_formulas',
      message: `At most ${p.maxMathCount} formulas are allowed.`,
      severity: 'error',
    })
  }
  for (const [expression, line] of expressions) {
    if (expression.length > p.maxMathChars) {
      issues.push({
        code: 'formula_too_long',
        message: `A formula can have at most ${p.maxMathChars} characters.`,
        line,
        severity: 'error',
      })
    }
    const found = FORBIDDEN_TEX.exec(expression)
    if (found) {
      issues.push({
        code: 'forbidden_tex',
        message: `The command \\${found[1]} is not allowed in formulas.`,
        line,
        severity: 'error',
      })
    }
  }
  return issues
}

function linkIssues(masked: string): Issue[] {
  const targets: Array<[string, number]> = []
  for (const m of masked.matchAll(LINK)) targets.push([m[1]!, m.index!])
  for (const m of masked.matchAll(AUTOLINK)) targets.push([m[1]!, m.index!])
  return targets
    .filter(([target]) => !(target.startsWith('https://') || target.startsWith('#') || target === ''))
    .map(([, pos]) => ({
      code: 'link_scheme',
      message: 'Links must start with https://.',
      line: lineAt(masked, pos),
      severity: 'error' as const,
    }))
}

function imageIssues(masked: string, p: (typeof PROFILES)[RichTextProfile]): Issue[] {
  const issues: Issue[] = []
  let count = 0
  for (const m of masked.matchAll(IMAGE)) {
    count += 1
    const line = lineAt(masked, m.index!)
    if (!ATTACHMENT.test(m[2]!)) {
      issues.push({
        code: 'image_not_attachment',
        message: 'Images must be uploaded; use ![alt](attachment:id).',
        line,
        severity: 'error',
      })
    } else if (!m[1]!.trim()) {
      issues.push({
        code: 'missing_alt',
        message: 'This image has no alt text.',
        line,
        severity: p.altRequired ? 'error' : 'warning',
      })
    }
  }
  if (count > p.maxImages) {
    issues.push({ code: 'too_many_images', message: `At most ${p.maxImages} images are allowed.`, severity: 'error' })
  }
  return issues
}

/** All problems with `markdown` under `profile`, sorted by line (whole-body issues first). Errors block a save. */
export function lint(markdown: string, profile: RichTextProfile = 'note'): Issue[] {
  const p = PROFILES[profile]
  const issues: Issue[] = []
  if (markdown.length > p.maxChars && charCount(markdown) > p.maxChars) {
    issues.push({
      code: 'too_long',
      message: `The text can have at most ${p.maxChars.toLocaleString('en-IN')} characters.`,
      severity: 'error',
    })
  }
  const lines = maskCode(markdown)
  const masked = lines.join('\n')
  issues.push(...headingIssues(lines, p), ...ruleIssues(lines, p), ...tableIssues(lines, p))
  issues.push(...mathIssues(masked, p), ...linkIssues(masked), ...imageIssues(masked, p))
  lines.forEach((line, index) => {
    const n = index + 1
    if (!p.taskLists && TASK.test(line)) {
      issues.push({
        code: 'task_list_not_allowed',
        message: 'Task lists are not allowed here.',
        line: n,
        severity: 'error',
      })
    }
    if (FOOTNOTE.test(line)) {
      issues.push({ code: 'footnote_not_allowed', message: 'Footnotes are not supported.', line: n, severity: 'error' })
    }
    if (HTML_TAG.test(line.replace(AUTOLINK, ''))) {
      issues.push({
        code: 'raw_html',
        message: 'HTML is shown as plain text, not rendered.',
        line: n,
        severity: 'warning',
      })
    }
  })
  return issues.sort((a, b) => (a.line ?? 0) - (b.line ?? 0) || (a.code < b.code ? -1 : a.code > b.code ? 1 : 0))
}

export const errorsOf = (issues: Issue[]) => issues.filter((i) => i.severity === 'error')

/** The uploaded images a body uses, in order, with their alt text (empty when decorative or missing). */
export function attachmentRefs(markdown: string): ImageRef[] {
  const masked = maskCode(markdown).join('\n')
  const refs: ImageRef[] = []
  for (const m of masked.matchAll(IMAGE)) {
    const found = ATTACHMENT.exec(m[2]!)
    if (found) refs.push({ attachmentId: found[1]!.toLowerCase(), alt: m[1]!.trim(), line: lineAt(masked, m.index!) })
  }
  return refs
}

/** Images without alt text: the editor warns before saving and offers "Mark decorative". */
export const imagesMissingAlt = (markdown: string) => attachmentRefs(markdown).filter((ref) => ref.alt === '')
