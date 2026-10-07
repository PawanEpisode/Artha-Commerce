/* eslint-disable @typescript-eslint/no-non-null-assertion -- regex groups and indexed access are guaranteed by the patterns above them */
/** Canonical text and plain-text extraction: the twin of `sanitise` and `plain_text` in `apps/api/core/richtext.py`. */

// Bidirectional overrides and the byte-order mark can make text read differently from how it is stored. The zero-width
// joiners U+200C and U+200D are NOT touched: Devanagari needs them.
// eslint-disable-next-line no-control-regex
const CONTROL = /[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]/g
const BIDI = /[\u202A-\u202E\u2066-\u2069\uFEFF]/g

/** Canonical form to store: LF newlines, no control or bidi-override characters. Never changes visible text. */
export const sanitise = (markdown: string) =>
  markdown.replace(/\r\n/g, '\n').replace(/\r/g, '\n').replace(CONTROL, '').replace(BIDI, '')

/** Number of characters as the server counts them (code points, not UTF-16 units). */
export function charCount(text: string): number {
  let count = 0
  for (const _ of text) count += 1
  return count
}

export const FENCE = /^ {0,3}(`{3,}|~{3,})(.*)$/
export const CODE_SPAN = /(`+)(?!`).+?(?<!`)\1(?!`)/g
export const AUTOLINK = /<([A-Za-z][A-Za-z0-9+.-]*:[^>\s]*)>/g

/** The lines with fenced blocks and inline code blanked out (same line count), so no rule fires inside code. */
export function maskCode(markdown: string): string[] {
  const lines: string[] = []
  let fence: string | null = null
  for (const line of markdown.split('\n')) {
    const match = FENCE.exec(line)
    if (fence) {
      const closes = match && match[1]![0] === fence[0] && match[1]!.length >= fence.length
      if (closes && !match![2]!.trim()) fence = null
      lines.push('')
    } else if (match) {
      fence = match[1]!
      lines.push('')
    } else {
      lines.push(line.replace(CODE_SPAN, (m) => ' '.repeat(m.length)))
    }
  }
  return lines
}

const PLAIN_STEPS: Array<[RegExp, string]> = [
  [/!\[([^\]\n]*)\]\([^)\n]*\)/g, '$1'], // image: its alt text
  [/\[([^\]\n]*)\]\([^)\n]*\)/g, '$1'], // link: its text
  [AUTOLINK, '$1'], // <https://...>: the address
  [/<\/?[A-Za-z][^<>\n]*>|<!--|-->/g, ' '], // raw HTML tags: the markup, not the words inside
  [/^ {0,3}#{1,6}\s+/gm, ''], // heading marker
  [/^ {0,3}>+\s?/gm, ''], // blockquote
  [/^\s*(?:[-*+]|\d+[.)])\s+(?:\[[ xX]\]\s+)?/gm, ''], // list and task markers
  [/^\s*\|?\s*:?-+:?\s*(?:\|\s*:?-+:?\s*)+\|?\s*$/gm, ''], // table delimiter row
  [/^ {0,3}([-*_])(?: *\1){2,} *$|^ {0,3}=+ *$/gm, ''], // rules and setext underlines
  [/(?<!\\)\|/g, ' '], // table cell separators
  [/(\*\*|__|~~|\*|(?<![A-Za-z0-9])_|_(?![A-Za-z0-9]))/g, ''], // emphasis markers
  [/(?<!\\)\$+/g, ''], // math delimiters: the formula text stays searchable
  [/\\([\\`*_{}[\]()#+\-.!|$])/g, '$1'], // backslash escapes (after the delimiters: `\$` is a dollar)
]

/**
 * The words of a body without Markdown syntax, one line per block, for search and snippets. Code keeps its text.
 * Formulas keep their TeX source (a student can search "frac"), without the `$` delimiters.
 */
export function plainText(markdown: string): string {
  const kept: Array<['code' | 'md', string]> = []
  let fence: string | null = null
  for (const line of sanitise(markdown).split('\n')) {
    const match = FENCE.exec(line)
    if (fence) {
      if (match && match[1]![0] === fence[0] && match[1]!.length >= fence.length && !match[2]!.trim()) fence = null
      else kept.push(['code', line])
    } else if (match) {
      fence = match[1]!
    } else {
      kept.push(['md', line])
    }
  }
  const out: string[] = []
  for (const [kind, raw] of kept) {
    let line = raw
    if (kind === 'md') {
      const spans: string[] = [] // code spans are set aside so nothing below rewrites their text
      line = line.replace(CODE_SPAN, (m) => {
        spans.push(m.replace(/^`+|`+$/g, '').trim())
        return `\x00${spans.length - 1}\x00`
      })
      for (const [pattern, replacement] of PLAIN_STEPS) line = line.replace(pattern, replacement)
      // eslint-disable-next-line no-control-regex
      line = line.replace(/\x00(\d+)\x00/g, (_m, i: string) => spans[Number(i)]!)
    }
    const words = line.split(/\s+/).filter(Boolean).join(' ')
    if (words) out.push(words)
  }
  return out.join('\n')
}
