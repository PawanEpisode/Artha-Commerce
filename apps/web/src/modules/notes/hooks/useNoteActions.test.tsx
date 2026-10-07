import { beforeEach, describe, expect, it, vi } from 'vitest'

import { makeNote } from '../lib/testing'

const notify = vi.hoisted(() => ({ restoredByEdit: vi.fn(), overwritten: vi.fn() }))
vi.mock('../lib/notify', () => ({ notify, UNDO_MS: 10_000 }))
vi.mock('~/modules/observability', () => ({ track: vi.fn(), ageBucket: () => '1-7d' }))
vi.mock('~/modules/personalization', () => ({ useOnline: () => true }))

import { reportPatch } from './useNoteActions'

beforeEach(() => vi.clearAllMocks())

describe('reportPatch', () => {
  it('says nothing for an ordinary save', () => {
    reportPatch({ ...makeNote(), merged: false })
    expect(notify.restoredByEdit).not.toHaveBeenCalled()
    expect(notify.overwritten).not.toHaveBeenCalled()
  })

  it('tells the student when an edit brought a trashed note back', () => {
    reportPatch({ ...makeNote(), restored: true })
    expect(notify.restoredByEdit).toHaveBeenCalledTimes(1)
  })

  it('names the fields another device had changed', () => {
    reportPatch({ ...makeNote(), overwritten: ['pinned', 'chapter_id'] })
    expect(notify.overwritten).toHaveBeenCalledWith(['pinned', 'chapter_id'])
  })
})
