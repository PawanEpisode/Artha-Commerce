import { beforeEach, describe, expect, it, vi } from 'vitest'

const api = vi.hoisted(() => vi.fn())
vi.mock('~/lib/api', async (original) => ({ ...(await original<Record<string, unknown>>()), api }))

import { getTodayThought } from './api'

beforeEach(() => api.mockReset())

describe('getTodayThought', () => {
  it('reads the line from the thought endpoint', async () => {
    const thought = { id: 'm1', body: 'Start small.', attribution: null, shown_on: '2026-10-07' }
    api.mockResolvedValue({ thought })
    await expect(getTodayThought()).resolves.toEqual(thought)
    expect(api).toHaveBeenCalledWith('/notifications/thought/today/')
  })

  it('returns null when there is no line for this student', async () => {
    api.mockResolvedValue({ thought: null })
    await expect(getTodayThought()).resolves.toBeNull()
  })

  it('rejects a response that breaks the contract', async () => {
    api.mockResolvedValue({ thought: { id: 'm1' } })
    await expect(getTodayThought()).rejects.toThrow()
  })
})
