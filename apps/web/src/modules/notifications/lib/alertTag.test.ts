import { beforeEach, describe, expect, it, vi } from 'vitest'

const track = vi.hoisted(() => vi.fn())
vi.mock('~/modules/observability', () => ({ track }))

import { reportLocalAlert, timerAlertTag } from './alertTag'

beforeEach(() => track.mockClear())

describe('timerAlertTag (FR-N5)', () => {
  it('is the string the API puts in the push payload: timer:<client_id>', () => {
    expect(timerAlertTag('6f1c')).toBe('timer:6f1c')
  })
  it('tells analytics which tag a local alert used, so a duplicate with the push is visible', () => {
    reportLocalAlert('timer:6f1c')
    expect(track).toHaveBeenCalledWith('local_alert_shown', { tag: 'timer:6f1c' })
  })
})
