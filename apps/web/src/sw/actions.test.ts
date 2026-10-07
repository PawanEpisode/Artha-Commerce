import { describe, expect, it, vi } from 'vitest'

import { ACTIONS_PATH, actionsUrl, parseTapAnswer, tokenFor, UNAVAILABLE_TITLE, unavailableContent } from './actions'
import { buildNotificationOptions, handleNotificationAction } from './handlers'
import { parsePushPayload } from './payload'
import type { ClientsLike, FetchLike, NotificationOptionsLike } from './types'

const ORIGIN = 'https://app.example.test'
const API = 'https://api.example.test'
const T1 = 'a'.repeat(43)
const T2 = 'B-_'.repeat(14) + 'c'

const alertPayload = JSON.stringify({
  v: 1,
  id: 'n1',
  category: 'timer',
  title: 'Round target reached',
  body: '25 minutes. The timer is still running.',
  tag: 'timer:abc',
  url: '/app/focus?n=n1',
  actions: [
    { id: 'start_break', title: 'Start break', token: T1 },
    { id: 'pause', title: 'Pause', token: T2 },
  ],
})

const alertData = () => buildNotificationOptions(parsePushPayload(alertPayload).content, 'dev').data

const answer = (outcome: string, extra: Record<string, unknown> = {}) => ({
  outcome,
  notification: {
    title: 'Timer paused',
    body: 'Your round is on hold.',
    tag: 'timer:abc',
    url: '/app/focus?n=n1',
    actions: [{ id: 'resume', title: 'Resume', token: T1 }],
    ...extra,
  },
})

function fetchReturning(status: number, body: unknown) {
  return vi.fn<FetchLike>().mockResolvedValue({ ok: status >= 200 && status < 300, status, json: async () => body })
}

function deps(fetch: FetchLike, apiBase: string | null = API) {
  const show = vi.fn<(title: string, options: NotificationOptionsLike) => Promise<void>>().mockResolvedValue(undefined)
  const clients = {
    matchAll: vi.fn().mockResolvedValue([]),
    openWindow: vi.fn().mockResolvedValue(undefined),
    claim: vi.fn(),
  } as unknown as ClientsLike & { openWindow: ReturnType<typeof vi.fn> }
  return { fetch, apiBase, show, swVersion: 'dev', clients, origin: ORIGIN }
}

describe('payload buttons', () => {
  it('keeps a well formed token and drops anything else', () => {
    const { content } = parsePushPayload(
      JSON.stringify({
        v: 1,
        title: 't',
        actions: [
          { id: 'pause', title: 'Pause', token: T1 },
          { id: 'x', title: 'X', token: 'short' },
        ],
      }),
    )
    expect(content.actions).toEqual([
      { id: 'pause', title: 'Pause', token: T1 },
      { id: 'x', title: 'X' },
    ])
  })

  it('puts the tokens and the tag in the notification data, keyed by button', () => {
    expect(alertData()).toMatchObject({ tag: 'timer:abc', tokens: { start_break: T1, pause: T2 } })
  })

  it('leaves the data without tokens when no button has one', () => {
    const { content } = parsePushPayload(JSON.stringify({ v: 1, title: 't', actions: [{ id: 'a', title: 'A' }] }))
    expect(buildNotificationOptions(content, 'dev').data.tokens).toBeUndefined()
  })
})

describe('actionsUrl and tokenFor', () => {
  it('builds the endpoint from the API origin only', () => {
    expect(actionsUrl('https://api.example.test/some/path')).toBe(`${API}${ACTIONS_PATH}`)
    expect(actionsUrl('http://localhost:8000')).toBe(`http://localhost:8000${ACTIONS_PATH}`)
    for (const bad of ['', null, undefined, 'not a url', 'javascript:alert(1)']) expect(actionsUrl(bad)).toBeNull()
  })

  it('finds the token of the tapped button and nothing else', () => {
    const data = alertData()
    expect(tokenFor(data, 'pause')).toBe(T2)
    expect(tokenFor(data, 'resume')).toBeNull()
    expect(tokenFor(data, '')).toBeNull()
    expect(tokenFor(null, 'pause')).toBeNull()
    expect(tokenFor({ tokens: { pause: 7 } }, 'pause')).toBeNull()
  })
})

describe('parseTapAnswer', () => {
  const fallback = { tag: 'timer:abc', url: '/app/focus?n=n1' }

  it('shows the confirmation with its follow-up button', () => {
    const content = parseTapAnswer(answer('done'), fallback)
    expect(content).toMatchObject({ title: 'Timer paused', tag: 'timer:abc', url: '/app/focus?n=n1' })
    expect(content.actions).toEqual([{ id: 'resume', title: 'Resume', token: T1 }])
  })

  it.each([null, 'x', {}, { notification: {} }, { notification: { title: '' } }])('falls back for %j', (bad) => {
    expect(parseTapAnswer(bad, fallback)).toEqual(unavailableContent(fallback))
  })

  it('never trusts a link or tag from the answer that is not allowed', () => {
    const content = parseTapAnswer(answer('done', { url: 'https://evil.example/x', tag: 'bad tag!' }), fallback)
    expect(content.url).toBe('/app')
    expect(content.tag).toBe('timer:abc')
  })
})

describe('handleNotificationAction', () => {
  it('posts the token, without credentials, and shows the confirmation in place of the alert', async () => {
    const fetch = fetchReturning(200, answer('done'))
    const d = deps(fetch)
    const outcome = await handleNotificationAction(d, 'pause', alertData())
    expect(outcome).toBe('done')
    expect(fetch).toHaveBeenCalledWith(`${API}${ACTIONS_PATH}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ token: T2 }),
      credentials: 'omit',
      mode: 'cors',
    })
    const [title, options] = d.show.mock.calls[0] ?? []
    expect(title).toBe('Timer paused')
    expect(options).toMatchObject({
      tag: 'timer:abc',
      renotify: false,
      actions: [{ action: 'resume', title: 'Resume' }],
    })
    expect(options?.data.tokens).toEqual({ resume: T1 })
    expect(d.clients.openWindow).not.toHaveBeenCalled()
  })

  it.each(['already', 'stale', 'needs_app'])('reports %s and still confirms without opening the app', async (o) => {
    const d = deps(fetchReturning(200, answer(o)))
    expect(await handleNotificationAction(d, 'pause', alertData())).toBe(o)
    expect(d.show).toHaveBeenCalledTimes(1)
    expect(d.clients.openWindow).not.toHaveBeenCalled()
  })

  it.each([
    ['a refused token', fetchReturning(400, { error: { code: 'action_unavailable' } })],
    ['switched off', fetchReturning(403, {})],
    ['throttled', fetchReturning(429, {})],
    ['offline', vi.fn<FetchLike>().mockRejectedValue(new TypeError('offline'))],
    ['a broken answer', fetchReturning(200, 'nonsense')],
  ])('shows "open the app" for %s', async (_, fetch) => {
    const d = deps(fetch)
    expect(await handleNotificationAction(d, 'start_break', alertData())).toBe('unavailable')
    const [title, options] = d.show.mock.calls[0] ?? []
    expect(title).toBe(UNAVAILABLE_TITLE)
    expect(options).toMatchObject({ tag: 'timer:abc', data: { url: '/app/focus?n=n1' } })
    expect(options?.actions).toBeUndefined()
  })

  it('behaves like a tap on the notification when the button has no token or there is no API address', async () => {
    for (const [action, apiBase] of [
      ['resume', API],
      ['pause', null],
    ] as const) {
      const fetch = fetchReturning(200, answer('done'))
      const d = deps(fetch, apiBase)
      expect(await handleNotificationAction(d, action, alertData())).toBe('opened')
      expect(fetch).not.toHaveBeenCalled()
      expect(d.clients.openWindow).toHaveBeenCalledWith(`${ORIGIN}/app/focus?n=n1`)
    }
  })
})
