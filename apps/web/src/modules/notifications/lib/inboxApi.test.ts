import { beforeEach, describe, expect, it, vi } from 'vitest'

const api = vi.hoisted(() => vi.fn())
vi.mock('~/lib/api', async (original) => ({ ...(await original<Record<string, unknown>>()), api }))

import { getInbox, postInboxRead } from './api'

const row = {
  id: 'n1',
  category: 'timer',
  category_label: 'Timer alerts',
  title: 'Round 1 done',
  body: '25 minutes.',
  deep_link: '/app/focus',
  read: false,
  created_at: '2026-10-05T04:30:00Z',
}

beforeEach(() => api.mockReset())

describe('getInbox', () => {
  it('asks for the first page with no query and checks the shape', async () => {
    api.mockResolvedValue({ results: [row], next_cursor: null, unread_count: 1 })
    const page = await getInbox()
    expect(api).toHaveBeenCalledWith('/notifications/inbox/')
    expect(page.results[0]?.title).toBe('Round 1 done')
  })

  it('passes the cursor and the limit, encoded', async () => {
    api.mockResolvedValue({ results: [], next_cursor: null, unread_count: 0 })
    await getInbox({ cursor: 'a+b/c=', limit: 20 })
    expect(api).toHaveBeenCalledWith('/notifications/inbox/?cursor=a%2Bb%2Fc%3D&limit=20')
  })

  it('rejects an answer that drifted from the contract', async () => {
    api.mockResolvedValue({ results: [{ ...row, read: 'no' }], next_cursor: null, unread_count: 1 })
    await expect(getInbox()).rejects.toThrow()
    api.mockResolvedValue({ results: [], next_cursor: null, unread_count: -1 })
    await expect(getInbox()).rejects.toThrow()
  })
})

describe('postInboxRead', () => {
  it('posts the ids and returns the new unread count', async () => {
    api.mockResolvedValue({ unread_count: 2 })
    await expect(postInboxRead({ ids: ['a', 'b'] })).resolves.toBe(2)
    expect(api).toHaveBeenCalledWith('/notifications/inbox/read/', { method: 'POST', body: '{"ids":["a","b"]}' })
  })

  it('posts all: true for mark all', async () => {
    api.mockResolvedValue({ unread_count: 0 })
    await postInboxRead({ all: true })
    expect(api).toHaveBeenCalledWith('/notifications/inbox/read/', { method: 'POST', body: '{"all":true}' })
  })
})
