import { beforeEach, describe, expect, it, vi } from 'vitest'

const api = vi.hoisted(() => vi.fn())

vi.mock('~/lib/api', async (original) => ({ ...(await original<Record<string, unknown>>()), api }))

import { getDigest, postDigestAnswer } from './api'

beforeEach(() => api.mockReset())

describe('digest API (W3.7)', () => {
  it('reads the offer and the switch', async () => {
    api.mockResolvedValue({ offer: true, enabled: false, time: '10:00' })
    expect(await getDigest()).toEqual({ offer: true, enabled: false, time: '10:00' })
    expect(api).toHaveBeenCalledWith('/notifications/digest/')
  })

  it('posts an answer and checks the reply', async () => {
    api.mockResolvedValue({ offer: false, enabled: true, time: '10:00' })
    expect((await postDigestAnswer('accept')).enabled).toBe(true)
    expect(api).toHaveBeenCalledWith('/notifications/digest/', {
      method: 'POST',
      body: JSON.stringify({ answer: 'accept' }),
    })
  })

  it('fails loudly on a reply of the wrong shape', async () => {
    api.mockResolvedValue({ offer: 'yes' })
    await expect(getDigest()).rejects.toThrow()
  })
})
