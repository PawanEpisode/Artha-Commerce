/**
 * A word-level difference between two versions of a card's text (R2-W4 leftover, "what changed"). Pure and small: the texts are
 * the first 300 characters of a version, so a plain longest-common-subsequence over words is enough. Whitespace is kept with the
 * word before it. Unchanged words are taken from the NEW text, so the new text comes back exactly from the 'same' and 'added'
 * segments, and the old text comes back up to its spacing from the 'same' and 'removed' ones.
 */
export type DiffKind = 'same' | 'added' | 'removed'
export interface DiffSegment {
  kind: DiffKind
  text: string
}

/** Above this many words on a side the diff is not worth the work: the whole text is shown as replaced. */
export const MAX_DIFF_WORDS = 400

/** Words with their trailing whitespace: "a  b " becomes ["a  ", "b "]; leading whitespace stays with the first word. */
export function tokenize(text: string): string[] {
  return text.match(/\s*\S+\s*|\s+/g) ?? []
}

const key = (token: string) => token.trim()

function push(out: DiffSegment[], kind: DiffKind, text: string) {
  const last = out[out.length - 1]
  if (last && last.kind === kind) last.text += text
  else out.push({ kind, text })
}

export function diffWords(before: string, after: string): DiffSegment[] {
  if (before === after) return before ? [{ kind: 'same', text: before }] : []
  const a = tokenize(before)
  const b = tokenize(after)
  const out: DiffSegment[] = []
  if (a.length > MAX_DIFF_WORDS || b.length > MAX_DIFF_WORDS) {
    if (before) out.push({ kind: 'removed', text: before })
    if (after) out.push({ kind: 'added', text: after })
    return out
  }
  // lcs is a flat table: cell (i, j) holds the length of the longest common run of a[i..] and b[j..].
  const w = b.length + 1
  const lcs = new Int32Array((a.length + 1) * w)
  const at = (i: number, j: number): number => lcs[i * w + j] ?? 0
  const words = (list: string[], n: number): string => list[n] ?? ''
  for (let i = a.length - 1; i >= 0; i--) {
    for (let j = b.length - 1; j >= 0; j--) {
      lcs[i * w + j] =
        key(words(a, i)) === key(words(b, j)) ? at(i + 1, j + 1) + 1 : Math.max(at(i + 1, j), at(i, j + 1))
    }
  }
  let i = 0
  let j = 0
  while (i < a.length && j < b.length) {
    if (key(words(a, i)) === key(words(b, j))) {
      push(out, 'same', words(b, j))
      i++
      j++
    } else if (at(i + 1, j) >= at(i, j + 1)) {
      push(out, 'removed', words(a, i++))
    } else {
      push(out, 'added', words(b, j++))
    }
  }
  while (i < a.length) push(out, 'removed', words(a, i++))
  while (j < b.length) push(out, 'added', words(b, j++))
  return out
}

/** True when the two texts differ in at least one word (a whitespace-only change is not a change she can see). */
export const hasWordChange = (segments: DiffSegment[]): boolean => segments.some((s) => s.kind !== 'same')
