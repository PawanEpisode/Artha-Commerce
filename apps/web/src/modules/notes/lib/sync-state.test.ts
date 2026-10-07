import { describe, expect, it } from 'vitest'

import { deriveSync, showUnsynced, UNSYNCED_TEXT } from './sync-state'

const base = { online: true, saving: false, queued: 0, parked: 0 }

describe('deriveSync', () => {
  it('is saved when nothing is pending', () => {
    expect(deriveSync(base)).toEqual({ state: 'saved', count: 0 })
  })

  it('shows saving while a save runs', () => {
    expect(deriveSync({ ...base, saving: true }).state).toBe('saving')
  })

  it('shows offline with the number of writes waiting', () => {
    expect(deriveSync({ ...base, online: false })).toEqual({ state: 'offline', count: 0 })
    expect(deriveSync({ ...base, queued: 3 })).toEqual({ state: 'offline', count: 3 })
  })

  it('puts a conflict above everything else', () => {
    expect(deriveSync({ online: false, saving: true, queued: 2, parked: 1 })).toEqual({ state: 'attention', count: 1 })
  })
})

describe('showUnsynced', () => {
  const note = { local_only: true, title: '', body_md: '', tags: [] as unknown[] }

  it('says nothing for an empty new note, a note the server knows or one that is not flagged', () => {
    expect(showUnsynced(note)).toBe(false)
    expect(showUnsynced({ ...note, local_only: undefined, body_md: 'x' })).toBe(false)
    expect(showUnsynced(undefined)).toBe(false)
  })

  it('says it once the note holds text, a title or a tag and the server has not confirmed it', () => {
    expect(showUnsynced({ ...note, body_md: 'x' })).toBe(true)
    expect(showUnsynced({ ...note, title: 'x' })).toBe(true)
    expect(showUnsynced({ ...note, tags: [{}] })).toBe(true)
    expect(UNSYNCED_TEXT).toBe('Saved on this device, waiting to sync')
  })
})
