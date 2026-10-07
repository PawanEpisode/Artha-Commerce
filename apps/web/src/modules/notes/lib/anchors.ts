/**
 * Text anchoring (ERD decision 4), the TypeScript twin of `apps/api/modules/notes/domain/anchoring.py`. The algorithm is
 * described in that module's docstring and is the contract: both sides read `anchoring_cases.json`, so port changes line
 * by line. No dependency: normalisation, exact search, 4-gram voting and a Sellers approximate match, all deterministic.
 * Offsets are UTF-16 units here (code points on the server): the same for Latin and Devanagari text, hints otherwise.
 */

export const CONTEXT_CHARS = 32
export const MAX_QUOTE = 1000
export const MIN_SCORE = 0.6
const MIN_FUZZY = 8
const MAX_FUZZY = 300
const LONG_PART = 120
const GRAM = 4
const BUCKET = 16
const MAX_GRAM_HITS = 20
const MIN_VOTES = 2
const MAX_WINDOWS = 3

const DROPPED = new Set([0xad, 0x200b, 0x200c, 0x200d, 0x200e, 0x200f, 0x2060, 0xfeff])
const HYPHENS = new Set(['-', '‐', '‑'])
const SPACES = new Set([
  9, 10, 11, 12, 13, 32, 0x85, 0xa0, 0x1680, 0x2000, 0x2001, 0x2002, 0x2003, 0x2004, 0x2005, 0x2006, 0x2007, 0x2008,
  0x2009, 0x200a, 0x2028, 0x2029, 0x202f, 0x205f, 0x3000,
])
const LINE_BREAKS = new Set(['\n', '\r', ' ', ' '])

export interface Normalised {
  text: string
  /** Original index where each normalised character begins. */
  starts: number[]
  /** Original index just after it. */
  ends: number[]
}

export interface Selector {
  quote_exact: string
  quote_prefix: string
  quote_suffix: string
  text_start: number
  text_end: number
}

export interface Located {
  start: number
  end: number
  score: number
}

type Span = [number, number]
type Found = [number, number, number] // normalised start, end, score

const isSpace = (c: string) => SPACES.has(c.codePointAt(0) as number)
const isDropped = (c: string) => DROPPED.has(c.codePointAt(0) as number)

function clusters(text: string): Span[] {
  const out: Span[] = []
  let i = 0
  for (const ch of text) {
    const last = out[out.length - 1]
    if (last && /^\p{M}/u.test(ch)) last[1] = i + ch.length
    else out.push([i, i + ch.length])
    i += ch.length
  }
  return out
}

const fold = (cluster: string): string[] => [...cluster.normalize('NFKC').toLowerCase()].filter((c) => !isDropped(c))

/** If the hyphen at cluster `i` ends a line inside a word, the cluster where the word continues. */
function joinAfter(parts: Span[], text: string, i: number): number | null {
  let sawBreak = false
  for (let j = i + 1; j < parts.length; j++) {
    const [s, e] = parts[j] as Span
    const first = [...text.slice(s, e)][0] as string
    if (isDropped(first) || isSpace(first)) sawBreak = sawBreak || LINE_BREAKS.has(first)
    else return sawBreak && /^[\p{Ll}\p{Lo}\p{Lm}]/u.test(first) ? j : null
  }
  return null
}

export function normaliseForMatch(text: string): Normalised {
  const parts = clusters(text)
  const chars: string[] = []
  const starts: number[] = []
  const ends: number[] = []
  let i = 0
  while (i < parts.length) {
    const [s, e] = parts[i] as Span
    const chunk = text.slice(s, e)
    const last = chars[chars.length - 1]
    if (HYPHENS.has(chunk) && last !== undefined && last !== ' ' && /^[\p{L}\p{M}]/u.test(last)) {
      const joined = joinAfter(parts, text, i)
      if (joined !== null) {
        i = joined
        continue
      }
    }
    for (const c of fold(chunk)) {
      if (isSpace(c)) {
        if (chars[chars.length - 1] === ' ') ends[ends.length - 1] = e
        else {
          chars.push(' ')
          starts.push(s)
          ends.push(e)
        }
      } else {
        chars.push(c)
        starts.push(s)
        ends.push(e)
      }
    }
    i++
  }
  return { text: chars.join(''), starts, ends }
}

/** The quote fields stored on a mark for the selection `pageText.slice(start, end)`. */
export function makeSelector(pageText: string, start: number, end: number): Selector {
  const from = Math.max(0, start)
  const to = Math.min(pageText.length, end)
  if (from >= to) throw new RangeError('empty selection')
  return {
    quote_exact: pageText.slice(from, to).slice(0, MAX_QUOTE),
    quote_prefix: pageText.slice(Math.max(0, from - CONTEXT_CHARS), from),
    quote_suffix: pageText.slice(to, to + CONTEXT_CHARS),
    text_start: from,
    text_end: to,
  }
}

const score4 = (x: number) => Math.floor(x * 10_000 + 0.5) / 10_000
const trimEndSpaces = (s: string) => s.replace(/ +$/, '')
const trimStartSpaces = (s: string) => s.replace(/^ +/, '')

function commonSuffix(a: string, b: string): number {
  let n = 0
  while (n < a.length && n < b.length && a[a.length - 1 - n] === b[b.length - 1 - n]) n++
  return n
}

function commonPrefix(a: string, b: string): number {
  let n = 0
  while (n < a.length && n < b.length && a[n] === b[n]) n++
  return n
}

/** Share of the stored prefix (read backwards) and suffix that agree with the text around [a, b); 0 to 1. */
function context(text: string, a: number, b: number, prefix: string, suffix: string): number {
  const pre = trimEndSpaces(prefix)
  const suf = trimStartSpaces(suffix)
  const parts: number[] = []
  if (pre) parts.push(Math.min(1, commonSuffix(pre, trimEndSpaces(text.slice(0, a))) / pre.length))
  if (suf) parts.push(Math.min(1, commonPrefix(suf, trimStartSpaces(text.slice(b))) / suf.length))
  return parts.length ? parts.reduce((x, y) => x + y, 0) / parts.length : 0
}

function exact(text: string, q: string, pre: string, suf: string, hint: number | null): Found | null {
  const found: number[] = []
  for (let i = text.indexOf(q); i !== -1; i = text.indexOf(q, i + 1)) found.push(i)
  if (found.length === 0) return null
  const ranked = found
    .map((i) => [-context(text, i, i + q.length, pre, suf), hint === null ? 0 : Math.abs(i - hint), i] as const)
    .sort((x, y) => x[0] - y[0] || x[1] - y[1] || x[2] - y[2])
  const [top, next] = ranked as [(typeof ranked)[number], (typeof ranked)[number] | undefined]
  const tie = next !== undefined && top[0] === next[0] && top[1] === next[1]
  return [top[2], top[2] + q.length, tie ? 0.75 : 1]
}

function windows(text: string, q: string): Span[] {
  const m = q.length
  const wanted = new Set<string>()
  for (let i = 0; i <= m - GRAM; i++) wanted.add(q.slice(i, i + GRAM))
  const hits = new Map<string, number[]>()
  for (let i = 0; i <= text.length - GRAM; i++) {
    const g = text.slice(i, i + GRAM)
    if (!wanted.has(g)) continue
    const list = hits.get(g)
    if (list) list.push(i)
    else hits.set(g, [i])
  }
  const votes = new Map<number, number>()
  for (let qi = 0; qi <= m - GRAM; qi++) {
    const positions = hits.get(q.slice(qi, qi + GRAM)) ?? []
    if (positions.length > MAX_GRAM_HITS) continue
    for (const pi of positions) {
      const bucket = Math.floor((pi - qi) / BUCKET)
      votes.set(bucket, (votes.get(bucket) ?? 0) + 1)
    }
  }
  const chosen: number[] = []
  const ordered = [...votes.entries()].sort((x, y) => y[1] - x[1] || x[0] - y[0])
  for (const [bucket, n] of ordered) {
    if (n >= MIN_VOTES && chosen.every((c) => Math.abs(bucket - c) > 2)) {
      chosen.push(bucket)
      if (chosen.length === MAX_WINDOWS) break
    }
  }
  const slack = Math.floor((m * 2) / 5) + 2
  return chosen.map((b): Span => [
    Math.max(0, b * BUCKET - slack),
    Math.min(text.length, b * BUCKET + BUCKET + m + slack),
  ])
}

/** Best approximate occurrence of `q` in `t`: [edits, start, end]. Ties: diagonal, then skip a quote char, then a page char. */
function sellers(q: string, t: string): [number, number, number] {
  const n = t.length
  let cost = new Array<number>(n + 1).fill(0)
  let start = Array.from({ length: n + 1 }, (_, j) => j)
  for (let i = 1; i <= q.length; i++) {
    const curCost = new Array<number>(n + 1).fill(0)
    const curStart = new Array<number>(n + 1).fill(0)
    curCost[0] = i
    for (let j = 1; j <= n; j++) {
      let best = (cost[j - 1] as number) + (q[i - 1] === t[j - 1] ? 0 : 1)
      let st = start[j - 1] as number
      if ((cost[j] as number) + 1 < best) {
        best = (cost[j] as number) + 1
        st = start[j] as number
      }
      if ((curCost[j - 1] as number) + 1 < best) {
        best = (curCost[j - 1] as number) + 1
        st = curStart[j - 1] as number
      }
      curCost[j] = best
      curStart[j] = st
    }
    cost = curCost
    start = curStart
  }
  let end = 0
  for (let j = 1; j <= n; j++) if ((cost[j] as number) < (cost[end] as number)) end = j
  return [cost[end] as number, start[end] as number, end]
}

function trim(text: string, from: number, to: number): Span {
  let a = from
  let b = to
  while (a < b && text[a] === ' ') a++
  while (b > a && text[b - 1] === ' ') b--
  return [a, b]
}

const before = (x: number[], y: number[]) => {
  for (let i = 0; i < x.length; i++) if (x[i] !== y[i]) return (x[i] as number) < (y[i] as number)
  return false
}

function fuzzy(text: string, q: string, pre: string, suf: string, hint: number | null): Found | null {
  const m = q.length
  if (m < MIN_FUZZY) return null
  let best: { key: number[]; a: number; b: number; sim: number } | null = null
  for (const [lo, hi] of windows(text, q)) {
    const [edits, s, e] = sellers(q, text.slice(lo, hi))
    if (edits > Math.floor((m * 2) / 5)) continue
    const [a, b] = trim(text, lo + s, lo + e)
    if (a >= b) continue
    const key = [edits, -context(text, a, b, pre, suf), hint === null ? 0 : Math.abs(a - hint), a]
    if (best === null || before(key, best.key)) best = { key, a, b, sim: 1 - edits / m }
  }
  return best === null ? null : [best.a, best.b, score4(best.sim)]
}

function locate(text: string, q: string, pre: string, suf: string, hint: number | null): Found | null {
  const hit = exact(text, q, pre, suf, hint)
  if (hit) return hit
  if (q.length <= MAX_FUZZY) return fuzzy(text, q, pre, suf, hint)
  const head = locate(text, q.slice(0, LONG_PART), pre, '', hint)
  const tail = locate(text, q.slice(-LONG_PART), '', suf, hint)
  if (!head || !tail || tail[1] <= head[0]) return null
  const span = tail[1] - head[0]
  return span >= 0.6 * q.length && span <= 1.6 * q.length
    ? [head[0], tail[1], score4(Math.min(head[2], tail[2]))]
    : null
}

function lowerBound(values: number[], target: number): number {
  let lo = 0
  let hi = values.length
  while (lo < hi) {
    const mid = (lo + hi) >> 1
    if ((values[mid] as number) < target) lo = mid + 1
    else hi = mid
  }
  return lo
}

/**
 * Where the quote is now, as offsets into `pageText` (the original, not the normalised text), or null when nothing scores
 * at least `MIN_SCORE`. `hintStart` is the stored `text_start`, used only to break ties.
 */
export function locateQuote(
  pageText: string,
  quoteExact: string,
  prefix = '',
  suffix = '',
  hintStart: number | null = null,
): Located | null {
  const page = normaliseForMatch(pageText)
  const q = trimEndSpaces(trimStartSpaces(normaliseForMatch(quoteExact).text))
  if (!q || !page.text) return null
  const hint = hintStart === null ? null : lowerBound(page.starts, hintStart)
  const found = locate(page.text, q, normaliseForMatch(prefix).text, normaliseForMatch(suffix).text, hint)
  if (found === null || found[2] < MIN_SCORE) return null
  return { start: page.starts[found[0]] as number, end: page.ends[found[1] - 1] as number, score: found[2] }
}
