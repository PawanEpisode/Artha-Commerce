/**
 * Client side of search: tidy the query before it is sent and find what to highlight in a snippet. The server does the
 * ranking and the reference-aware matching ("17(5)" is one token, not "17" and "5"); this keeps the two in step.
 */

export const MAX_QUERY_LENGTH = 200

/** Trim, collapse runs of whitespace and cut at the server's 200 character limit (code points, never mid-emoji). */
export function normaliseQuery(raw: string): string {
  return [...raw.trim().replace(/\s+/g, ' ')].slice(0, MAX_QUERY_LENGTH).join('')
}

export const isSearchable = (raw: string) => normaliseQuery(raw).length > 0

/** The words to highlight. Quoted phrases and references such as `17(5)` or `80C` stay whole. */
export function queryTerms(raw: string): string[] {
  const query = normaliseQuery(raw)
  const terms: string[] = []
  for (const match of query.matchAll(/"([^"]+)"|(\S+)/g)) {
    const term = (match[1] ?? match[2] ?? '').replace(/^["']|["']$/g, '').trim()
    if (term) terms.push(term)
  }
  return [...new Set(terms.map((t) => t.toLowerCase()))].sort((a, b) => b.length - a.length)
}

const escapeRegex = (text: string) => text.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')

export interface Piece {
  text: string
  match: boolean
}

/** Splits a snippet into plain and matching pieces, longest terms first, so `<mark>` can wrap the matches. */
export function splitHighlight(text: string, raw: string): Piece[] {
  const terms = queryTerms(raw)
  if (terms.length === 0 || text === '') return [{ text, match: false }]
  const pattern = new RegExp(`(${terms.map(escapeRegex).join('|')})`, 'gi')
  // With one capture group, split() alternates plain and matching pieces, so a piece is a match when it is a term.
  return text
    .split(pattern)
    .filter((piece) => piece !== '')
    .map((piece) => ({ text: piece, match: terms.includes(piece.toLowerCase()) }))
}

export type LengthBucket = '1-3' | '4-10' | '11-30' | '31+'

/** Analytics only ever sees the length of a query, in a range, never the query (PRD 10.1). */
export function queryLengthBucket(raw: string): LengthBucket {
  const n = [...normaliseQuery(raw)].length
  if (n <= 3) return '1-3'
  if (n <= 10) return '4-10'
  return n <= 30 ? '11-30' : '31+'
}

export type ResultBucket = '0' | '1-5' | '6-20' | '21+'
export const resultBucket = (n: number): ResultBucket => (n === 0 ? '0' : n <= 5 ? '1-5' : n <= 20 ? '6-20' : '21+')
