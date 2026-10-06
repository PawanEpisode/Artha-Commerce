import { describe, expect, it } from 'vitest'

import { pathKind, restoreEvent } from './visitAnalytics'

const now = new Date('2026-10-06T12:00:00Z')
const server = { path: '/app/syllabus/ca', search: '', at: '2026-10-06T10:00:00Z' }

describe('pathKind', () => {
  it('names the section, never an id', () => {
    expect(pathKind('/app/syllabus/abc/def')).toBe('syllabus')
    expect(pathKind('/app/tracker/reports')).toBe('tracker')
    expect(pathKind('/app')).toBe('home')
    expect(pathKind('/courses/ca')).toBe('other')
  })
})

describe('restoreEvent', () => {
  it('reports a restore from the server copy', () => {
    expect(restoreEvent('/app/syllabus/ca', server, null, now)).toEqual({
      path_kind: 'syllabus',
      age_bucket: '<1d',
      source: 'server',
    })
  })

  it('reports the device copy when it was the winner', () => {
    const local = { path: '/app/focus', search: '', at: '2026-10-06T11:30:00Z' }
    expect(restoreEvent('/app/focus', local, local, now)).toMatchObject({ source: 'local', age_bucket: '<1h' })
  })

  it('stays silent when something else won (deep link, home, onboarding)', () => {
    expect(restoreEvent('/app/tracker', server, null, now)).toBeNull()
    expect(restoreEvent('/app', server, null, now)).toBeNull()
    expect(restoreEvent('/app', null, null, now)).toBeNull()
  })

  it('includes the search in the match', () => {
    const v = { path: '/app/tracker/reports', search: 'range=week', at: '2026-10-06T11:59:00Z' }
    expect(restoreEvent('/app/tracker/reports?range=week', v, null, now)).not.toBeNull()
    expect(restoreEvent('/app/tracker/reports', v, null, now)).toBeNull()
  })
})
