import type { Fields } from './cardKinds'

export interface FieldConflict {
  field: string
  base: string
  mine: string
  theirs: string
}

export interface Merge {
  /** Fields that merged on their own: only one side changed, or both changed the same way. */
  merged: Fields
  /** Fields both sides changed differently. The student chooses. */
  conflicts: FieldConflict[]
}

/**
 * A three way merge of a card edit. `base` is what the student started from, `mine` her draft, `theirs` what the server
 * holds now. A field only one side touched keeps that change; a field both changed differently is a conflict.
 */
export function mergeFields(base: Fields, mine: Fields, theirs: Fields): Merge {
  const merged: Fields = {}
  const conflicts: FieldConflict[] = []
  const names = new Set([...Object.keys(base), ...Object.keys(mine), ...Object.keys(theirs)])
  for (const field of names) {
    const b = base[field] ?? ''
    const m = mine[field] ?? ''
    const t = theirs[field] ?? ''
    if (m === t) merged[field] = m
    else if (m === b) merged[field] = t
    else if (t === b) merged[field] = m
    else {
      merged[field] = m
      conflicts.push({ field, base: b, mine: m, theirs: t })
    }
  }
  return { merged, conflicts }
}

/** The merged fields after the student settled each conflict (`keep` is the field name to its choice). */
export function resolve(merge: Merge, choice: Record<string, 'mine' | 'theirs'>): Fields {
  const out = { ...merge.merged }
  for (const c of merge.conflicts) out[c.field] = choice[c.field] === 'theirs' ? c.theirs : c.mine
  return out
}
