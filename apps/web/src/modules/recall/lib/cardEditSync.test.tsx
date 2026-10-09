import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError } from '~/lib/api'

import { cardEditQueue, EDIT_QUEUE_MAX } from './cardEditQueue'
import { flushEdits } from './cardEditSync'

const err = (status: number, code: string, details?: unknown) =>
  new ApiError(status, 'x', { error: { code, message: 'm', details } })

const edit = (cardId: string, over: Record<string, unknown> = {}) => ({
  cardId,
  kind: 'pointer',
  baseRev: 3,
  base: { prompt_md: 'Q', answer_md: 'A' },
  fields: { prompt_md: 'My Q', answer_md: 'A' },
  importance: 'bullet' as const,
  tags: [],
  ...over,
})

beforeEach(() => window.localStorage.clear())

describe('the offline edit queue', () => {
  it('keeps one entry per card and the version she first started from', () => {
    cardEditQueue.put('u1', edit('c1'))
    cardEditQueue.put(
      'u1',
      edit('c1', { baseRev: 9, base: { prompt_md: 'newer' }, fields: { prompt_md: 'Second edit', answer_md: 'A' } }),
    )
    const [only, ...rest] = cardEditQueue.list('u1')
    expect(rest).toEqual([])
    expect(only).toMatchObject({
      baseRev: 3,
      base: { prompt_md: 'Q', answer_md: 'A' },
      fields: { prompt_md: 'Second edit' },
    })
    expect(cardEditQueue.waiting('u1')).toBe(1)
    expect(cardEditQueue.waiting('u2')).toBe(0)
  })

  it('refuses a new card past the limit instead of dropping something', () => {
    for (let i = 0; i < EDIT_QUEUE_MAX; i += 1) cardEditQueue.put('u1', edit(`c${i}`))
    expect(cardEditQueue.put('u1', edit('one-more'))).toBe('full')
    expect(cardEditQueue.put('u1', edit('c0', { fields: { prompt_md: 'again', answer_md: 'A' } }))).toBe('queued')
  })
})

describe('sending edits written offline', () => {
  it('sends each edit against the revision she started from and clears it', async () => {
    cardEditQueue.put('u1', edit('c1'))
    const patch = vi.fn().mockResolvedValue({})
    expect(await flushEdits('u1', patch)).toEqual({ sent: 1, needsAttention: 0, stopped: false })
    expect(patch).toHaveBeenCalledWith(
      'c1',
      expect.objectContaining({ base_rev: 3, fields: { prompt_md: 'My Q', answer_md: 'A' } }),
    )
    expect(cardEditQueue.list('u1')).toEqual([])
  })

  it('merges quietly when the other device changed a different part, then sends on the new revision', async () => {
    cardEditQueue.put('u1', edit('c1'))
    const patch = vi
      .fn()
      .mockRejectedValueOnce(
        err(409, 'edit_conflict', { server_fields: { prompt_md: 'Q', answer_md: 'Their A' }, rev: 6 }),
      )
      .mockResolvedValueOnce({})
    expect((await flushEdits('u1', patch)).sent).toBe(1)
    expect(patch.mock.calls[1]![1]).toMatchObject({ base_rev: 6, fields: { prompt_md: 'My Q', answer_md: 'Their A' } })
    expect(cardEditQueue.list('u1')).toEqual([])
  })

  it('marks an edit for the student when both sides changed the same part, and keeps her text', async () => {
    cardEditQueue.put('u1', edit('c1'))
    const patch = vi
      .fn()
      .mockRejectedValue(err(409, 'edit_conflict', { server_fields: { prompt_md: 'Their Q', answer_md: 'A' }, rev: 6 }))
    expect(await flushEdits('u1', patch)).toMatchObject({ sent: 0, needsAttention: 1 })
    const [kept] = cardEditQueue.list('u1')
    expect(kept?.fields.prompt_md).toBe('My Q')
    expect(kept?.attention).toMatchObject({ kind: 'conflict', rev: 6, theirs: { prompt_md: 'Their Q' } })
    // an entry that needs attention is not sent again behind her back
    await flushEdits('u1', patch)
    expect(patch).toHaveBeenCalledTimes(1)
  })

  it('marks an edit of a card deleted elsewhere, and one the server refuses', async () => {
    cardEditQueue.put('u1', edit('gone'))
    cardEditQueue.put('u1', edit('bad'))
    const patch = vi.fn((id: string) =>
      Promise.reject(
        id === 'gone'
          ? err(410, 'card_deleted')
          : err(422, 'invalid_fields', {
              errors: [{ field: 'prompt_md', code: 'math', message: 'The formula is not valid.' }],
            }),
      ),
    )
    expect((await flushEdits('u1', patch)).needsAttention).toBe(2)
    expect(cardEditQueue.get('u1', 'gone')?.attention).toEqual({ kind: 'deleted' })
    expect(cardEditQueue.get('u1', 'bad')?.attention).toEqual({ kind: 'invalid', message: 'The formula is not valid.' })
  })

  it('stops and keeps everything when the network fails', async () => {
    cardEditQueue.put('u1', edit('c1'))
    cardEditQueue.put('u1', edit('c2'))
    const patch = vi.fn().mockRejectedValue(new TypeError('Failed to fetch'))
    expect(await flushEdits('u1', patch)).toEqual({ sent: 0, needsAttention: 0, stopped: true })
    expect(patch).toHaveBeenCalledTimes(1)
    expect(cardEditQueue.waiting('u1')).toBe(2)
  })
})
