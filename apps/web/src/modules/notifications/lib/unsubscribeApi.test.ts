import { beforeEach, describe, expect, it, vi } from 'vitest'

const api = vi.hoisted(() => vi.fn())
vi.mock('~/lib/api', async (original) => ({ ...(await original<Record<string, unknown>>()), api }))

import { confirmUnsubscribe, previewUnsubscribe } from './api'

const RESULT = { category: 'progress', label: 'Weekly summary', unsubscribed: false }

beforeEach(() => api.mockReset())

describe('unsubscribe calls', () => {
  it('previews with the token in the query, encoded', async () => {
    api.mockResolvedValue(RESULT)
    await expect(previewUnsubscribe('a.b_c-d')).resolves.toEqual(RESULT)
    expect(api).toHaveBeenCalledWith('/notifications/unsubscribe/?t=a.b_c-d')
    await previewUnsubscribe('a b&c')
    expect(api).toHaveBeenLastCalledWith('/notifications/unsubscribe/?t=a%20b%26c')
  })

  it('confirms with a POST body', async () => {
    api.mockResolvedValue({ ...RESULT, unsubscribed: true })
    await expect(confirmUnsubscribe('tok')).resolves.toMatchObject({ unsubscribed: true })
    expect(api).toHaveBeenCalledWith('/notifications/unsubscribe/', {
      method: 'POST',
      body: JSON.stringify({ token: 'tok' }),
    })
  })

  it('rejects an answer that breaks the contract', async () => {
    api.mockResolvedValue({ category: 'progress' })
    await expect(previewUnsubscribe('tok')).rejects.toThrow()
  })
})
