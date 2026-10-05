import { toast } from '@artha/design-system'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { notify } from './notify'

describe('focus notify', () => {
  const success = vi.spyOn(toast, 'success')
  const info = vi.spyOn(toast, 'info')

  beforeEach(() => {
    success.mockReturnValue('id')
    info.mockReturnValue('id')
  })
  afterEach(() => vi.clearAllMocks())

  it('tells a round from a break', () => {
    notify.started('focus', 2)
    notify.started('long_break', 4)
    expect(success).toHaveBeenCalledWith('Round 2 started', expect.anything())
    expect(info).toHaveBeenCalledWith('Long break started', expect.anything())
  })

  it('says offline once, whatever the action was', () => {
    notify.paused(true)
    notify.extended(true)
    expect(info.mock.calls.map((c) => c[0])).toEqual(['Saved on this device', 'Saved on this device'])
  })

  it('separates a saved partial round from one that was too short or discarded', () => {
    notify.ended({ saved: true, outcome: 'saved' })
    notify.ended({ saved: true, outcome: 'too_short' })
    notify.ended({ saved: false })
    expect(success).toHaveBeenCalledWith('Saved as a partial round', expect.anything())
    expect(info.mock.calls.map((c) => c[0])).toEqual(['Under a minute, so not saved', 'Round discarded'])
  })

  it('shows what comes next when a phase ends', () => {
    notify.phaseEnded({ title: 'Focus round done', body: 'Time for a short break.' })
    expect(success).toHaveBeenCalledWith(
      'Focus round done',
      expect.objectContaining({ description: 'Time for a short break.' }),
    )
  })
})
