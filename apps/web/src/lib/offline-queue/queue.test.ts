import 'fake-indexeddb/auto'

import { beforeEach, describe, expect, it, vi } from 'vitest'

import {
  clearOfflineQueue,
  enqueue,
  flush,
  isTransient,
  parkedConflicts,
  pending,
  type QueuedWrite,
  resetFlushState,
  resetOfflineQueue,
  resolveParked,
  withFlushLock,
} from '.'

const entry = (clientId: string, queuedAt: number, userId = 'u1'): QueuedWrite => ({
  clientId,
  userId,
  method: 'PUT',
  path: `/coverage/topics/${clientId}/`,
  body: { done: true, client_id: clientId },
  queuedAt,
})

const httpError = (status: number) => Object.assign(new Error(`HTTP ${status}`), { status })

beforeEach(async () => {
  resetOfflineQueue()
  resetFlushState()
  await clearOfflineQueue()
})

describe('isTransient', () => {
  it('retries network failures, timeouts, throttling and server errors', () => {
    for (const e of [new TypeError('Failed to fetch'), httpError(408), httpError(429), httpError(500), httpError(503)])
      expect(isTransient(e)).toBe(true)
  })

  it('does not retry client errors', () => {
    for (const e of [httpError(400), httpError(403), httpError(404), httpError(422), new Error('x'), null])
      expect(isTransient(e)).toBe(false)
  })
})

describe('queue storage', () => {
  it('returns the user’s writes oldest first and never another user’s', async () => {
    await enqueue(entry('b', 20))
    await enqueue(entry('a', 10))
    await enqueue(entry('other', 5, 'u2'))
    expect((await pending('u1')).map((e) => e.clientId)).toEqual(['a', 'b'])
    expect((await pending('u2')).map((e) => e.clientId)).toEqual(['other'])
  })

  it('keeps one entry when the same client id is queued twice', async () => {
    await enqueue(entry('a', 10))
    await enqueue(entry('a', 11))
    expect(await pending('u1')).toHaveLength(1)
  })

  it('survives a fresh connection to the database (a reload)', async () => {
    await enqueue(entry('a', 10))
    resetOfflineQueue()
    expect((await pending('u1')).map((e) => e.clientId)).toEqual(['a'])
  })
})

describe('flush', () => {
  it('replays in order with the original client ids and empties the queue', async () => {
    await enqueue(entry('a', 10))
    await enqueue(entry('b', 20))
    const send = vi.fn().mockResolvedValue({})
    const result = await flush('u1', send)
    expect(result).toEqual({ sent: 2, dropped: 0, remaining: 0 })
    expect(send.mock.calls.map(([e]) => (e as QueuedWrite).body.client_id)).toEqual(['a', 'b'])
    expect(await pending('u1')).toHaveLength(0)
  })

  it('stops at the first transient failure and keeps the rest, in order', async () => {
    await enqueue(entry('a', 10))
    await enqueue(entry('b', 20))
    await enqueue(entry('c', 30))
    const send = vi.fn().mockResolvedValueOnce({}).mockRejectedValueOnce(new TypeError('offline'))
    const result = await flush('u1', send)
    expect(result).toEqual({ sent: 1, dropped: 0, remaining: 2 })
    expect(send).toHaveBeenCalledTimes(2)
    expect((await pending('u1')).map((e) => e.clientId)).toEqual(['b', 'c'])
  })

  it('drops a write the server rejects for good and carries on', async () => {
    await enqueue(entry('a', 10))
    await enqueue(entry('b', 20))
    const send = vi.fn().mockRejectedValueOnce(httpError(404)).mockResolvedValueOnce({})
    const result = await flush('u1', send)
    expect(result).toEqual({ sent: 1, dropped: 1, remaining: 0 })
    expect(await pending('u1')).toHaveLength(0)
  })

  it('retrying after a failure sends the same client id again, so the server can ignore the repeat', async () => {
    await enqueue(entry('a', 10))
    const send = vi.fn().mockRejectedValueOnce(httpError(503)).mockResolvedValueOnce({})
    await flush('u1', send)
    await flush('u1', send)
    const ids = send.mock.calls.map(([e]) => (e as QueuedWrite).clientId)
    expect(ids).toEqual(['a', 'a'])
    expect(await pending('u1')).toHaveLength(0)
  })

  it('shares one run between concurrent callers', async () => {
    await enqueue(entry('a', 10))
    const send = vi.fn().mockResolvedValue({})
    await Promise.all([flush('u1', send), flush('u1', send)])
    expect(send).toHaveBeenCalledTimes(1)
  })

  it('never replays another user’s writes', async () => {
    await enqueue(entry('theirs', 10, 'u2'))
    const send = vi.fn().mockResolvedValue({})
    await flush('u1', send)
    expect(send).not.toHaveBeenCalled()
    expect(await pending('u2')).toHaveLength(1)
  })
})

describe('scopes', () => {
  const inScope = (clientId: string, queuedAt: number, scope: string): QueuedWrite => ({
    ...entry(clientId, queuedAt),
    scope,
  })

  it('keeps lanes apart: entries without a scope belong to the shared lane', async () => {
    await enqueue(entry('core1', 10))
    await enqueue(inScope('note1', 5, 'notes'))
    expect((await pending('u1')).map((e) => e.clientId)).toEqual(['core1'])
    expect((await pending('u1', 'notes')).map((e) => e.clientId)).toEqual(['note1'])
  })

  it('flushes one lane without touching the others', async () => {
    await enqueue(entry('core1', 10))
    await enqueue(inScope('note1', 5, 'notes'))
    const send = vi.fn().mockResolvedValue({})
    await flush('u1', send, { scope: 'notes' })
    expect(send.mock.calls.map(([e]) => (e as QueuedWrite).clientId)).toEqual(['note1'])
    expect(await pending('u1')).toHaveLength(1)
  })

  it('a stuck lane does not block another lane', async () => {
    await enqueue(entry('core1', 10))
    await enqueue(inScope('note1', 5, 'notes'))
    const stuck = vi.fn().mockRejectedValue(new TypeError('offline'))
    const fine = vi.fn().mockResolvedValue({})
    await flush('u1', stuck, { scope: 'notes' })
    const result = await flush('u1', fine)
    expect(result.sent).toBe(1)
    expect(await pending('u1', 'notes')).toHaveLength(1)
  })
})

describe('parked conflicts', () => {
  const conflict = Object.assign(new Error('conflict'), { status: 409 })
  const parkOn = (error: unknown) => ((error as { status?: number }).status === 409 ? { theirs: 'x' } : null)

  it('parks a refused write, keeps flushing the writes behind it and reports the count', async () => {
    await enqueue(entry('a', 10))
    await enqueue(entry('b', 20))
    const send = vi.fn().mockRejectedValueOnce(conflict).mockResolvedValueOnce({})
    const onParked = vi.fn()
    const result = await flush('u1', send, { parkOn, onParked })
    expect(result).toEqual({ sent: 1, dropped: 0, remaining: 0, parked: 1 })
    expect(onParked).toHaveBeenCalledOnce()
    expect(await pending('u1')).toHaveLength(0)
    const parked = await parkedConflicts('u1', 'core')
    expect(parked.map((p) => p.clientId)).toEqual(['a'])
    expect(parked[0]!.detail).toEqual({ theirs: 'x' })
  })

  it('forgets a conflict once it is resolved, and never shows it to another user', async () => {
    await enqueue(entry('a', 10))
    await flush('u1', vi.fn().mockRejectedValue(conflict), { parkOn })
    expect(await parkedConflicts('u2', 'core')).toHaveLength(0)
    await resolveParked('a')
    expect(await parkedConflicts('u1', 'core')).toHaveLength(0)
  })

  it('still drops an error that is not a conflict', async () => {
    await enqueue(entry('a', 10))
    const result = await flush('u1', vi.fn().mockRejectedValue(httpError(422)), { parkOn })
    expect(result).toEqual({ sent: 0, dropped: 1, remaining: 0 })
  })
})

describe('flush lock', () => {
  it('runs the task when the browser has no Web Locks', async () => {
    await expect(withFlushLock('x', async () => 7)).resolves.toBe(7)
  })

  it('reports busy and sends nothing when another tab holds the lock', async () => {
    const locks = { request: vi.fn(async (_n: string, _o: unknown, cb: (l: null) => Promise<unknown>) => cb(null)) }
    vi.stubGlobal('navigator', { locks })
    await enqueue(entry('a', 10))
    const send = vi.fn()
    const result = await flush('u1', send)
    vi.unstubAllGlobals()
    expect(send).not.toHaveBeenCalled()
    expect(result).toEqual({ sent: 0, dropped: 0, remaining: 1, busy: true })
    expect(locks.request).toHaveBeenCalledWith('artha-flush:u1:core', { ifAvailable: true }, expect.any(Function))
  })
})
