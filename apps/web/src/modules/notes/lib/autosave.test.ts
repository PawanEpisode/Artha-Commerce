import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { AUTOSAVE_DELAY_MS, createAutosave } from './autosave'

beforeEach(() => vi.useFakeTimers())
afterEach(() => vi.useRealTimers())

const deferred = () => {
  let resolve!: () => void
  const promise = new Promise<void>((r) => (resolve = r))
  return { promise, resolve }
}

describe('createAutosave', () => {
  it('saves 2 seconds after typing stops, and only once for a burst of typing', async () => {
    const save = vi.fn().mockResolvedValue(undefined)
    const autosave = createAutosave({ save })
    autosave.touch()
    await vi.advanceTimersByTimeAsync(1500)
    autosave.touch()
    await vi.advanceTimersByTimeAsync(1500)
    expect(save).not.toHaveBeenCalled()
    await vi.advanceTimersByTimeAsync(AUTOSAVE_DELAY_MS - 1500)
    expect(save).toHaveBeenCalledTimes(1)
    expect(autosave.status()).toBe('idle')
  })

  it('flush saves at once and cancels the countdown', async () => {
    const save = vi.fn().mockResolvedValue(undefined)
    const autosave = createAutosave({ save })
    autosave.touch()
    expect(autosave.status()).toBe('dirty')
    await autosave.flush()
    expect(save).toHaveBeenCalledTimes(1)
    await vi.advanceTimersByTimeAsync(5000)
    expect(save).toHaveBeenCalledTimes(1)
  })

  it('does nothing on flush when nothing changed', async () => {
    const save = vi.fn().mockResolvedValue(undefined)
    await createAutosave({ save }).flush()
    expect(save).not.toHaveBeenCalled()
  })

  it('never runs two saves at once and saves again for text typed during a save', async () => {
    const first = deferred()
    const save = vi.fn().mockReturnValueOnce(first.promise).mockResolvedValue(undefined)
    const autosave = createAutosave({ save })
    autosave.touch()
    await vi.advanceTimersByTimeAsync(AUTOSAVE_DELAY_MS)
    expect(autosave.status()).toBe('saving')
    autosave.touch()
    await vi.advanceTimersByTimeAsync(AUTOSAVE_DELAY_MS)
    expect(save).toHaveBeenCalledTimes(1)
    first.resolve()
    await vi.advanceTimersByTimeAsync(0)
    expect(save).toHaveBeenCalledTimes(2)
  })

  it('stays dirty after a failed save so the next try sends the text again', async () => {
    const save = vi.fn().mockRejectedValueOnce(new Error('offline')).mockResolvedValue(undefined)
    const autosave = createAutosave({ save })
    autosave.touch()
    await vi.advanceTimersByTimeAsync(AUTOSAVE_DELAY_MS)
    expect(autosave.status()).toBe('dirty')
    await autosave.flush()
    expect(save).toHaveBeenCalledTimes(2)
    expect(autosave.status()).toBe('idle')
  })

  it('cancel drops the pending save', async () => {
    const save = vi.fn().mockResolvedValue(undefined)
    const autosave = createAutosave({ save })
    autosave.touch()
    autosave.cancel()
    await vi.advanceTimersByTimeAsync(5000)
    expect(save).not.toHaveBeenCalled()
  })
})
