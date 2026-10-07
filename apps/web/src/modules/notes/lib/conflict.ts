/* eslint-disable @typescript-eslint/no-non-null-assertion -- the table and both line arrays are indexed inside their own bounds */
import { both } from './reconcile'
import type { NoteConflictDetail, Resolution } from './types'

/** One line of a comparison: unchanged, only in theirs (removed from mine) or only in mine. */
export interface DiffLine {
  kind: 'same' | 'theirs' | 'mine'
  text: string
}

/**
 * A line diff of their text against mine (longest common subsequence). Enough to show the student what differs in the
 * conflict sheet and the version compare view; notes are a few hundred lines at most.
 */
export function diffLines(theirs: string, mine: string): DiffLine[] {
  const a = theirs.split('\n')
  const b = mine.split('\n')
  const table: number[][] = Array.from({ length: a.length + 1 }, () => new Array<number>(b.length + 1).fill(0))
  for (let i = a.length - 1; i >= 0; i--) {
    for (let j = b.length - 1; j >= 0; j--) {
      table[i]![j] = a[i] === b[j] ? table[i + 1]![j + 1]! + 1 : Math.max(table[i + 1]![j]!, table[i]![j + 1]!)
    }
  }
  const out: DiffLine[] = []
  let i = 0
  let j = 0
  while (i < a.length && j < b.length) {
    if (a[i] === b[j]) {
      out.push({ kind: 'same', text: a[i]! })
      i++
      j++
    } else if (table[i + 1]![j]! >= table[i]![j + 1]!) {
      out.push({ kind: 'theirs', text: a[i++]! })
    } else {
      out.push({ kind: 'mine', text: b[j++]! })
    }
  }
  while (i < a.length) out.push({ kind: 'theirs', text: a[i++]! })
  while (j < b.length) out.push({ kind: 'mine', text: b[j++]! })
  return out
}

export const hasChanges = (lines: DiffLine[]) => lines.some((line) => line.kind !== 'same')

/** What "Keep both" produces, shown before the student chooses: theirs, a `---` line, then mine (the server does the same). */
export const bothText = both

/** The text each choice leaves in the note. */
export function resolvedBody(resolution: Resolution, detail: NoteConflictDetail, mineBody: string): string {
  if (resolution === 'theirs') return detail.theirs.body_md
  if (resolution === 'mine') return mineBody
  return bothText(detail.theirs.body_md, mineBody)
}
