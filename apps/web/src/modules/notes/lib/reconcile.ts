/**
 * Field-level compare-and-set (ERD 3.6), the TypeScript twin of the reconcile functions in
 * `apps/api/modules/notes/domain/merge.py`, driven by the same `reconcile_cases.json`. The server is the authority; the
 * client uses this to decide, before it sends, whether a queued write is likely to conflict and to show the conflict
 * sheet at once. Rules are in the Python docstrings. One deliberate difference: the server merges text with
 * diff-match-patch on characters; this twin diffs on words (no dependency), so two edits inside one word conflict here
 * while the server may merge them. The fixtures pin the cases where both must agree; the server's answer always wins.
 */
import type { Resolution } from './types'

export const BOTH_SEPARATOR = '\n\n---\n\n'

interface Edit {
  start: number
  end: number
  text: string
}

export interface MergeResult {
  /** Clean: the merge. Conflict: the merge with every conflicting region resolved to `theirs`. */
  text: string
  clean: boolean
  conflicts: number
}

export interface FieldConflict {
  field: string
  mine: string
  theirs: string
  merged: string
}

export interface ReconcileResult {
  accepted: Record<string, unknown>
  overwritten: string[]
  conflict: FieldConflict | null
}

export function deepEqual(a: unknown, b: unknown): boolean {
  if (a === b) return true
  if (typeof a !== 'object' || typeof b !== 'object' || a === null || b === null) return false
  if (Array.isArray(a) !== Array.isArray(b)) return false
  const keysA = Object.keys(a)
  const keysB = Object.keys(b)
  return (
    keysA.length === keysB.length &&
    keysA.every(
      (k) => Object.hasOwn(b, k) && deepEqual((a as Record<string, unknown>)[k], (b as Record<string, unknown>)[k]),
    )
  )
}

/** The one span that turns `base` into `other`: everything between their common start and common end. */
function singleEdit(base: string, other: string): Edit {
  let start = 0
  while (start < base.length && start < other.length && base[start] === other[start]) start++
  let endBase = base.length
  let endOther = other.length
  while (endBase > start && endOther > start && base[endBase - 1] === other[endOther - 1]) {
    endBase--
    endOther--
  }
  return { start, end: endBase, text: other.slice(start, endOther) }
}

const TOKEN = /[\p{L}\p{N}\p{M}_]+|\s+|[^\p{L}\p{N}\p{M}\s_]/gu
const MAX_CELLS = 4_000_000

/**
 * The edits that turn `base` into `other`, found on words (a word, a run of spaces or one symbol is one token) with a
 * longest common subsequence. Word granularity stands in for the server's character diff plus semantic clean-up: two
 * edits in different words are two edits, two edits inside one word are one (so they conflict). Very long texts fall
 * back to a single span.
 */
function edits(base: string, other: string): Edit[] {
  if (base === other) return []
  const a = base.match(TOKEN) ?? []
  const b = other.match(TOKEN) ?? []
  if (a.length * b.length > MAX_CELLS) return [singleEdit(base, other)]
  let lo = 0
  while (lo < a.length && lo < b.length && a[lo] === b[lo]) lo++
  let hiA = a.length
  let hiB = b.length
  while (hiA > lo && hiB > lo && a[hiA - 1] === b[hiB - 1]) {
    hiA--
    hiB--
  }
  const width = hiB - lo + 1
  const table = new Uint32Array((hiA - lo + 1) * width)
  const cell = (i: number, j: number) => (i - lo) * width + (j - lo)
  for (let i = hiA - 1; i >= lo; i--) {
    for (let j = hiB - 1; j >= lo; j--) {
      table[cell(i, j)] =
        a[i] === b[j]
          ? (table[cell(i + 1, j + 1)] as number) + 1
          : Math.max(table[cell(i + 1, j)] as number, table[cell(i, j + 1)] as number)
    }
  }
  const offset: number[] = [0]
  for (const token of a) offset.push((offset[offset.length - 1] as number) + token.length)
  const out: Edit[] = []
  let run: Edit | null = null
  const flush = () => {
    if (run) out.push(run)
    run = null
  }
  const open = (i: number): Edit => (run ??= { start: offset[i] as number, end: offset[i] as number, text: '' })
  let i = lo
  let j = lo
  while (i < hiA || j < hiB) {
    if (i < hiA && j < hiB && a[i] === b[j]) {
      flush()
      i++
      j++
    } else if (j >= hiB || (i < hiA && (table[cell(i + 1, j)] as number) >= (table[cell(i, j + 1)] as number))) {
      open(i).end = offset[i + 1] as number
      i++
    } else {
      open(i).text += b[j]
      j++
    }
  }
  flush()
  return out
}

const touches = (a: Edit, b: Edit) => a.start <= b.end && b.start <= a.end
const sameEdit = (a: Edit, b: Edit) => a.start === b.start && a.end === b.end && a.text === b.text

function apply(base: string, edits: Edit[]): string {
  const ordered = [...edits].sort((a, b) => a.start - b.start || a.end - b.end)
  let out = ''
  let pos = 0
  for (const e of ordered) {
    out += base.slice(pos, e.start) + e.text
    pos = e.end
  }
  return out + base.slice(pos)
}

/** 3-way text merge of `mine` and `theirs`, both derived from `base`. Identical edits count once; overlap is a conflict. */
export function merge3Text(base: string, mine: string, theirs: string): MergeResult {
  if (mine === theirs || base === theirs) return { text: mine, clean: true, conflicts: 0 }
  if (base === mine) return { text: theirs, clean: true, conflicts: 0 }
  const theirEdits = edits(base, theirs)
  const chosen = [...theirEdits] // theirs always stands; mine is added where it does not touch theirs
  let conflicts = 0
  for (const m of edits(base, mine)) {
    const clashing = theirEdits.filter((t) => touches(m, t))
    if (clashing.length === 0) chosen.push(m)
    else if (!clashing.every((t) => sameEdit(m, t))) conflicts++
  }
  return { text: apply(base, chosen), clean: conflicts === 0, conflicts }
}

/** `merge3Text`, clean only when stable: replaying either side's write on the merged text changes nothing (see Python). */
export function merge3Stable(base: string, mine: string, theirs: string): MergeResult {
  const result = merge3Text(base, mine, theirs)
  if (!result.clean || mine === theirs || base === mine || base === theirs) return result
  for (const side of [mine, theirs]) {
    const replay = merge3Text(base, side, result.text)
    if (!(replay.clean && replay.text === result.text)) return { text: theirs, clean: false, conflicts: 1 }
  }
  return result
}

/** Theirs, a `---` rule, then mine. Nothing is lost; an empty side is not padded with a rule. */
export function both(theirs: string, mine: string): string {
  if (!mine.trim()) return theirs
  if (!theirs.trim()) return mine
  return `${theirs}${BOTH_SEPARATOR}${mine}`
}

/** The text a parked conflict becomes. */
export function resolveConflict(resolution: Resolution, mine: string, theirs: string): string {
  if (resolution === 'mine') return mine
  if (resolution === 'theirs') return theirs
  return both(theirs, mine)
}

const asText = (value: unknown) => (value === null || value === undefined ? '' : String(value))

export function reconcileFields(
  stored: Record<string, unknown>,
  base: Record<string, unknown>,
  incoming: Record<string, unknown>,
  options: { textFields?: string[]; geometryFields?: string[] } = {},
): ReconcileResult {
  const textFields = options.textFields ?? ['comment']
  const geometryFields = options.geometryFields ?? ['geometry']
  if (textFields.some((f) => geometryFields.includes(f))) throw new Error('a field cannot be both text and geometry')
  const accepted: Record<string, unknown> = {}
  const overwritten: string[] = []
  let conflict: FieldConflict | null = null
  for (const [field, value] of Object.entries(incoming)) {
    const have = stored[field] ?? null
    const known = Object.hasOwn(base, field)
    if (deepEqual(have, value) || (known && deepEqual(have, base[field]))) {
      accepted[field] = value
    } else if (textFields.includes(field)) {
      const mine = asText(value)
      const theirs = asText(have)
      const merged: MergeResult = known
        ? merge3Stable(asText(base[field]), mine, theirs)
        : { text: theirs, clean: false, conflicts: 1 }
      if (merged.clean) accepted[field] = merged.text
      else conflict ??= { field, mine, theirs, merged: merged.text }
    } else {
      accepted[field] = value
      if (known) overwritten.push(field)
    }
  }
  return { accepted, overwritten: overwritten.sort(), conflict }
}

export type EditVsDeleteAction = 'apply' | 'restore' | 'noop' | 'keep'

/** Edit versus delete: edit wins, nothing is lost (ERD 3.6). */
export function resolveEditVsDelete(input: {
  storedDeleted: boolean
  storedRev: number
  baseRev: number
  op: 'edit' | 'delete'
}): { action: EditVsDeleteAction; restored: boolean } {
  if (input.op === 'edit') return { action: input.storedDeleted ? 'restore' : 'apply', restored: input.storedDeleted }
  if (input.storedDeleted) return { action: 'noop', restored: false }
  return { action: input.storedRev > input.baseRev ? 'keep' : 'apply', restored: false }
}
