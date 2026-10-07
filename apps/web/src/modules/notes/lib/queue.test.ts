import { describe, expect, it } from 'vitest'

import { ApiError } from '~/lib/api'

import { mergePatchBodies, parkOnConflict, patchKey } from './queue'

const NOTE = '3f2b8c1e-5a4d-4e9b-8c7a-1d2e3f4a5b6c'

describe('mergePatchBodies', () => {
  it('keeps the first edit’s base and takes the newest text', () => {
    const merged = mergePatchBodies(
      { base_rev: 3, base_body_md: 'server text', body_md: 'first edit', title: 'A' },
      { base_rev: 3, base_body_md: 'server text', body_md: 'second edit' },
    )
    expect(merged).toEqual({ base_rev: 3, base_body_md: 'server text', body_md: 'second edit', title: 'A' })
  })

  it('never lets a waiting edit’s base move to a later revision', () => {
    expect(mergePatchBodies({ base_rev: 3, body_md: 'a' }, { base_rev: 4, body_md: 'b' }).base_rev).toBe(3)
  })

  it('merges other fields such as pin and chapter and drops an old resolution', () => {
    const merged = mergePatchBodies({ base_rev: 1, resolution: 'mine', body_md: 'a' }, { base_rev: 1, pinned: true })
    expect(merged).toEqual({ base_rev: 1, body_md: 'a', pinned: true })
  })
})

describe('patchKey', () => {
  it('gives each note one place in the queue for its edits', () => {
    expect(patchKey('n1')).toBe('patch:n1')
  })
})

describe('parkOnConflict', () => {
  const entry = { clientId: 'x', userId: 'u', method: 'PATCH' as const, path: `/notes/${NOTE}/`, body: {}, queuedAt: 1 }
  const conflict = (code: string, status = 409) =>
    new ApiError(status, 'x', { error: { code, details: { theirs: { rev: 2 }, mine: {}, merged: null } } })

  it('parks a note conflict with the note id and what the server holds', () => {
    const parked = parkOnConflict(conflict('note_conflict'), entry)
    expect(parked?.noteId).toBe(NOTE)
    expect(parked?.detail.theirs.rev).toBe(2)
  })

  it('ignores other errors, so the queue drops or retries them as usual', () => {
    expect(parkOnConflict(conflict('tag_exists'), entry)).toBeNull()
    expect(parkOnConflict(conflict('note_conflict', 422), entry)).toBeNull()
    expect(parkOnConflict(new TypeError('offline'), entry)).toBeNull()
  })
})

describe('mergePatchBodies and the last seen values', () => {
  it('keeps the oldest value of each field the student last saw', () => {
    const merged = mergePatchBodies(
      { base_rev: 1, base: { pinned: false } },
      { base_rev: 1, base: { pinned: true, chapter_id: 'c0' } },
    )
    expect(merged.base).toEqual({ pinned: false, chapter_id: 'c0' })
  })
})
