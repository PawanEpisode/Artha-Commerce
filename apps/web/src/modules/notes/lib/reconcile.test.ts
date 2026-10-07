import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

import { describe, expect, it } from 'vitest'

import {
  both,
  deepEqual,
  merge3Stable,
  reconcileFields,
  type ReconcileResult,
  resolveConflict,
  resolveEditVsDelete,
} from './reconcile'
import type { Resolution } from './types'

type Fields = Record<string, unknown>
// The same fixtures the Python tests use. The twin diffs on words, so it may report a conflict where the server (characters)
// merges cleanly; those cases carry `ts_may_conflict`. Where the twin says clean it must match the server.
const fixtures = JSON.parse(
  readFileSync(
    fileURLToPath(new URL('../../../../../api/modules/notes/tests/fixtures/reconcile_cases.json', import.meta.url)),
    'utf8',
  ),
) as {
  reconcile: {
    name: string
    stored: Fields
    base: Fields
    incoming: Fields
    expected: ReconcileResult
    ts_may_conflict?: boolean
  }[]
  merge3: {
    name: string
    base: string
    mine: string
    theirs: string
    text: string
    clean: boolean
    ts_may_conflict?: boolean
  }[]
  resolve: { name: string; resolution: Resolution; mine: string; theirs: string; expected: string }[]
  edit_vs_delete: {
    name: string
    stored_deleted: boolean
    stored_rev: number
    base_rev: number
    op: 'edit' | 'delete'
    expected: { action: string; restored: boolean }
  }[]
}

describe('reconcileFields', () => {
  it.each(fixtures.reconcile.map((c) => [c.name, c] as const))('%s', (_n, c) => {
    const got = reconcileFields(c.stored, c.base, c.incoming)
    if (c.ts_may_conflict && got.conflict) {
      expect(got.conflict.field).toBe('comment')
      return
    }
    expect(got).toEqual(c.expected)
  })

  it('keeps text and geometry fields apart', () => {
    expect(() => reconcileFields({}, {}, {}, { textFields: ['x'], geometryFields: ['x'] })).toThrow()
  })
})

describe('merge3Stable', () => {
  it.each(fixtures.merge3.map((c) => [c.name, c] as const))('%s', (_n, c) => {
    const got = merge3Stable(c.base, c.mine, c.theirs)
    if (c.ts_may_conflict && !got.clean) return
    expect({ text: got.text, clean: got.clean }).toEqual({ text: c.text, clean: c.clean })
  })
})

describe('resolveConflict and edit versus delete', () => {
  it.each(fixtures.resolve.map((c) => [c.name, c] as const))('%s', (_n, c) => {
    expect(resolveConflict(c.resolution, c.mine, c.theirs)).toBe(c.expected)
  })

  it.each(fixtures.edit_vs_delete.map((c) => [c.name, c] as const))('%s', (_n, c) => {
    expect(
      resolveEditVsDelete({ storedDeleted: c.stored_deleted, storedRev: c.stored_rev, baseRev: c.base_rev, op: c.op }),
    ).toEqual(c.expected)
  })

  it('both is theirs, a rule, then mine', () => {
    expect(both('a', 'b')).toBe('a\n\n---\n\nb')
  })
})

describe('deepEqual', () => {
  it('compares nested geometry by value', () => {
    expect(deepEqual({ quads: [[0.1, 0.2]] }, { quads: [[0.1, 0.2]] })).toBe(true)
    expect(deepEqual({ quads: [[0.1, 0.2]] }, { quads: [[0.1, 0.3]] })).toBe(false)
    expect(deepEqual([1], { 0: 1 })).toBe(false)
    expect(deepEqual(null, '')).toBe(false)
  })
})
