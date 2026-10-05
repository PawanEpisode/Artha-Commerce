import { toast } from '@artha/design-system'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { notify } from './notify'

describe('tracker notify', () => {
  const success = vi.spyOn(toast, 'success')
  const info = vi.spyOn(toast, 'info')
  const warning = vi.spyOn(toast, 'warning')

  beforeEach(() => {
    success.mockReturnValue('id')
    info.mockReturnValue('id')
    warning.mockReturnValue('id')
  })
  afterEach(() => vi.clearAllMocks())

  it('words a saved stopwatch in hours and minutes', () => {
    notify.stopwatchStopped({ saved: true, outcome: 'saved', seconds: 5400 })
    expect(success).toHaveBeenCalledWith('Saved 1 h 30 m of study time', expect.anything())
  })

  it('says when time under a minute was not saved', () => {
    notify.stopwatchStopped({ saved: true, outcome: 'too_short', seconds: 30 })
    expect(info).toHaveBeenCalledWith('Under a minute, so not saved', expect.anything())
    expect(success).not.toHaveBeenCalled()
  })

  it('uses one shared id for offline-queued writes so they never stack', () => {
    notify.stopwatchStarted(true)
    notify.sessionAdded(true)
    const ids = info.mock.calls.map((c) => c[1]?.id)
    expect(ids).toEqual(['tracker-offline', 'tracker-offline'])
    expect(info.mock.calls[0]?.[0]).toBe('Saved on this device')
  })

  it('offers Undo only when given an undo handler', () => {
    const onUndo = vi.fn()
    notify.sessionDeleted(90 * 60, onUndo)
    notify.sessionSplit()
    const [deleted, split] = success.mock.calls
    expect(deleted?.[0]).toBe('Deleted 1 h 30 m of study time')
    deleted?.[1]?.action?.onClick()
    expect(onUndo).toHaveBeenCalled()
    expect(split?.[1]?.action).toBeUndefined()
  })

  it('reports dropped sync entries as a warning', () => {
    notify.syncConflict(2)
    expect(warning).toHaveBeenCalledWith('2 changes could not be applied', expect.anything())
  })
})
