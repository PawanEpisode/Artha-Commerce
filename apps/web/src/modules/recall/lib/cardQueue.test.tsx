import { beforeEach, describe, expect, it } from 'vitest'

import { CARD_QUEUE_MAX, cardQueue } from './cardQueue'

describe('cards written offline', () => {
  const body = (id: string) => ({ client_id: id, kind: 'pointer', fields: { prompt_md: 'q', answer_md: 'a' } })
  beforeEach(() => window.localStorage.clear())

  it('queues once per client id, per student, and removes on request', () => {
    expect(cardQueue.add('u1', body('a'))).toBe('queued')
    expect(cardQueue.add('u1', body('a'))).toBe('queued')
    expect(cardQueue.count('u1')).toBe(1)
    expect(cardQueue.count('u2')).toBe(0)
    cardQueue.remove('u1', 'a')
    expect(cardQueue.count('u1')).toBe(0)
  })

  it('refuses past the limit instead of dropping silently', () => {
    for (let i = 0; i < CARD_QUEUE_MAX; i += 1) cardQueue.add('u1', body(`id${i}`))
    expect(cardQueue.add('u1', body('one-too-many'))).toBe('full')
    expect(cardQueue.count('u1')).toBe(CARD_QUEUE_MAX)
  })
})
