import { describe, expect, it } from 'vitest'

import { deriveSync } from './sync-state'

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
