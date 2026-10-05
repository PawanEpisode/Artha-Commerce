import { describe, expect, it } from 'vitest'

import { elapsedSeconds } from './duration'
import { localPause, localResume, localStart } from './stopwatchLocal'

const ctx = { subject_id: null, chapter_id: null, activity_type: 'reading' as const }

describe('offline stopwatch transitions', () => {
  it('starts running at the corrected moment', () => {
    const sw = localStart('2026-10-05T04:00:00Z', 'cid', ctx)
    expect(sw.status).toBe('running')
    expect(sw.client_id).toBe('cid')
    expect(elapsedSeconds(sw, Date.parse('2026-10-05T04:10:00Z'))).toBe(600)
  })

  it('pauses, then resumes with the pause taken out of the total', () => {
    const started = localStart('2026-10-05T04:00:00Z', 'cid', ctx)
    const paused = localPause(started, '2026-10-05T04:10:00Z')
    expect(paused.status).toBe('paused')
    expect(paused.pause_count).toBe(1)
    expect(paused.elapsed_seconds).toBe(600)
    const resumed = localResume(paused, '2026-10-05T04:15:00Z')
    expect(resumed.status).toBe('running')
    expect(resumed.paused_total_seconds).toBe(300)
    expect(elapsedSeconds(resumed, Date.parse('2026-10-05T04:25:00Z'))).toBe(1200)
  })

  it('ignores a repeated pause or resume', () => {
    const started = localStart('2026-10-05T04:00:00Z', 'cid', ctx)
    expect(localResume(started, '2026-10-05T04:01:00Z')).toBe(started)
    const paused = localPause(started, '2026-10-05T04:10:00Z')
    expect(localPause(paused, '2026-10-05T04:11:00Z')).toBe(paused)
  })
})
