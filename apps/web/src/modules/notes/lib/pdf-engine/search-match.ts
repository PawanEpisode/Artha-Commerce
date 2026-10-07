/**
 * Finding a query in page text: case, accents of Latin text, hyphenation at line ends, odd spaces and zero-width
 * characters are ignored the same way as for mark anchoring (`lib/anchors.ts`), and the answer is in offsets of the
 * ORIGINAL text so a hit can be drawn on the page. Pure.
 */
import { type Normalised, normaliseForMatch } from '../anchors'

export interface TextMatch {
  start: number
  end: number
}

export const MIN_QUERY = 2

export function findMatches(text: string, query: string, limit = 500): TextMatch[] {
  const needle = normaliseForMatch(query.trim()).text
  if (needle.length < MIN_QUERY) return []
  const hay: Normalised = normaliseForMatch(text)
  const out: TextMatch[] = []
  let from = 0
  while (out.length < limit) {
    const at = hay.text.indexOf(needle, from)
    if (at === -1) break
    const last = at + needle.length - 1
    out.push({ start: hay.starts[at] as number, end: hay.ends[last] as number })
    from = at + Math.max(1, needle.length)
  }
  return out
}

/** About `radius` characters either side of a match, on one line, with an ellipsis where it was cut. */
export function snippetAround(text: string, match: TextMatch, radius = 40): string {
  const from = Math.max(0, match.start - radius)
  const to = Math.min(text.length, match.end + radius)
  const body = text.slice(from, to).replace(/\s+/g, ' ').trim()
  return `${from > 0 ? '…' : ''}${body}${to < text.length ? '…' : ''}`
}
