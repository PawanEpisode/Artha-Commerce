import 'fake-indexeddb/auto'

import { beforeEach, describe, expect, it, vi } from 'vitest'

import {
  clearOfflineQueue,
  enqueue,
  flush,
  isTransient,
  pending,
  type QueuedWrite,
  resetOfflineQueue,
} from './offlineQueue'

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
