import { describe, expect, it, vi } from 'vitest'

import {
  buildNotificationOptions,
  chooseClient,
  handleNotificationClick,
  handlePush,
  handleSubscriptionChange,
  NOTIFICATION_ICON,
  readNotificationData,
} from './handlers'
import { SW_MESSAGE_SUBSCRIPTION_CHANGED } from './messages'
import { fallbackContent, parsePushPayload } from './payload'
import type { ClientsLike, WindowClientLike } from './types'

const ORIGIN = 'https://app.example.test'
const payload = JSON.stringify({
  v: 1,
  id: 'n1',
  category: 'timer',
  title: 'Round 2 done',
  body: 'Take 5.',
  tag: 'timer:abc',
  url: '/app/focus?n=n1',
  actions: [{ id: 'break', title: 'Start break' }],
})

describe('handlePush', () => {
  it('shows one notification with the payload tag, renotify off and the worker version', async () => {
    const show = vi.fn().mockResolvedValue(undefined)
    await handlePush({ show, swVersion: 'abc1234' }, payload)
    expect(show).toHaveBeenCalledTimes(1)
    const [title, options] = show.mock.calls[0] as [string, ReturnType<typeof buildNotificationOptions>]
    expect(title).toBe('Round 2 done')
    expect(options).toMatchObject({
      body: 'Take 5.',
      tag: 'timer:abc',
      renotify: false,
      icon: NOTIFICATION_ICON,
      data: { url: '/app/focus?n=n1', id: 'n1', category: 'timer', swVersion: 'abc1234' },
      actions: [{ action: 'break', title: 'Start break' }],
    })
  })

  it.each([null, '', 'garbage', '{"v":9}', '{"v":1}'])('still shows a generic alert for %s', async (raw) => {
    const show = vi.fn().mockResolvedValue(undefined)
    await handlePush({ show, swVersion: 'dev' }, raw)
    expect(show).toHaveBeenCalledTimes(1)
    expect(show.mock.calls[0]?.[0]).toBe(fallbackContent().title)
    expect(show.mock.calls[0]?.[1]).toMatchObject({ renotify: false, data: { url: '/app' } })
  })

  it('leaves out the actions key when there are none', () => {
    const options = buildNotificationOptions(parsePushPayload('{"v":1,"title":"x"}').content, 'dev')
    expect(options).not.toHaveProperty('actions')
  })
})

describe('readNotificationData', () => {
  it('re-validates the link stored on the notification', () => {
    expect(readNotificationData({ url: '/app/tracker' }).url).toBe('/app/tracker')
    expect(readNotificationData({ url: '//evil.example' }).url).toBe('/app')
    expect(readNotificationData(undefined).url).toBe('/app')
    expect(readNotificationData('x').url).toBe('/app')
  })
})

const client = (patch: Partial<WindowClientLike> & { url: string }): WindowClientLike => ({
  focused: false,
  visibilityState: 'hidden',
  focus: vi.fn().mockResolvedValue(undefined),
  navigate: vi.fn().mockResolvedValue(undefined),
  ...patch,
})

describe('chooseClient', () => {
  it('prefers the focused tab, then a visible one, then any same-origin tab', () => {
    const hidden = client({ url: `${ORIGIN}/a` })
    const visible = client({ url: `${ORIGIN}/b`, visibilityState: 'visible' })
    const focused = client({ url: `${ORIGIN}/c`, focused: true })
    expect(chooseClient([hidden, visible, focused], ORIGIN)).toBe(focused)
    expect(chooseClient([hidden, visible], ORIGIN)).toBe(visible)
    expect(chooseClient([hidden], ORIGIN)).toBe(hidden)
  })

  it('ignores tabs of other origins and unparseable urls', () => {
    const other = client({ url: 'https://evil.example/app', focused: true })
    const broken = client({ url: 'not a url' })
    expect(chooseClient([other, broken], ORIGIN)).toBeNull()
    expect(chooseClient([], ORIGIN)).toBeNull()
  })
})

function clientsOf(list: WindowClientLike[]): ClientsLike & { openWindow: ReturnType<typeof vi.fn> } {
  return {
    matchAll: vi.fn().mockResolvedValue(list),
    openWindow: vi.fn().mockResolvedValue(undefined),
    claim: vi.fn().mockResolvedValue(undefined),
  }
}

describe('handleNotificationClick', () => {
  it('opens a new window when no tab is open', async () => {
    const clients = clientsOf([])
    await expect(handleNotificationClick({ clients, origin: ORIGIN }, { url: '/app/focus?n=1' })).resolves.toBe(
      'opened',
    )
    expect(clients.openWindow).toHaveBeenCalledWith(`${ORIGIN}/app/focus?n=1`)
  })

  it('focuses an open tab and sends it to the link', async () => {
    const tab = client({ url: `${ORIGIN}/app/tracker`, visibilityState: 'visible' })
    const clients = clientsOf([tab])
    await expect(handleNotificationClick({ clients, origin: ORIGIN }, { url: '/app/focus?n=1' })).resolves.toBe(
      'navigated',
    )
    expect(tab.focus).toHaveBeenCalled()
    expect(tab.navigate).toHaveBeenCalledWith(`${ORIGIN}/app/focus?n=1`)
    expect(clients.openWindow).not.toHaveBeenCalled()
  })

  it('only focuses when the tab is already on the link', async () => {
    const tab = client({ url: `${ORIGIN}/app/focus?n=1` })
    const clients = clientsOf([tab])
    await expect(handleNotificationClick({ clients, origin: ORIGIN }, { url: '/app/focus?n=1' })).resolves.toBe(
      'focused',
    )
    expect(tab.navigate).not.toHaveBeenCalled()
  })

  it('opens a window when the tab cannot navigate or focus fails', async () => {
    const noNavigate = client({ url: `${ORIGIN}/app`, navigate: undefined })
    const a = clientsOf([noNavigate])
    await expect(handleNotificationClick({ clients: a, origin: ORIGIN }, { url: '/app/focus' })).resolves.toBe('opened')

    const failing = client({ url: `${ORIGIN}/app`, focus: vi.fn().mockRejectedValue(new Error('gone')) })
    const b = clientsOf([failing])
    await expect(handleNotificationClick({ clients: b, origin: ORIGIN }, { url: '/app/focus' })).resolves.toBe('opened')
    expect(b.openWindow).toHaveBeenCalledWith(`${ORIGIN}/app/focus`)
  })

  it('opens a window when the tab list cannot be read', async () => {
    const clients = clientsOf([])
    clients.matchAll = vi.fn().mockRejectedValue(new Error('no'))
    await expect(handleNotificationClick({ clients, origin: ORIGIN }, { url: '/app' })).resolves.toBe('opened')
  })

  it.each(['//evil.example/x', 'https://evil.example/app', '/\\evil.example', '/admin', undefined])(
    'never opens a refused link (%s)',
    async (url) => {
      const clients = clientsOf([])
      await handleNotificationClick({ clients, origin: ORIGIN }, { url })
      expect(clients.openWindow).toHaveBeenCalledWith(`${ORIGIN}/app`)
    },
  )
})

describe('handleSubscriptionChange', () => {
  const key = new Uint8Array(65)
  const tab = () => ({ ...client({ url: `${ORIGIN}/app` }), postMessage: vi.fn() })

  it('re-subscribes with the old key and tells open pages', async () => {
    const page = tab()
    const subscribe = vi.fn().mockResolvedValue({})
    const outcome = await handleSubscriptionChange(
      { subscribe, fallbackKey: null, clients: clientsOf([page]) },
      { options: { applicationServerKey: key.buffer } },
    )
    expect(outcome).toBe('resubscribed')
    expect(subscribe).toHaveBeenCalledWith(key.buffer)
    expect(page.postMessage).toHaveBeenCalledWith({ type: SW_MESSAGE_SUBSCRIPTION_CHANGED, resubscribed: true })
  })

  it('falls back to the key baked into the build', async () => {
    const subscribe = vi.fn().mockResolvedValue({})
    const outcome = await handleSubscriptionChange({ subscribe, fallbackKey: key, clients: clientsOf([]) }, null)
    expect(outcome).toBe('resubscribed')
    expect(subscribe).toHaveBeenCalledWith(key)
  })

  it('gives up quietly without a key, and says so to the pages', async () => {
    const page = tab()
    const subscribe = vi.fn()
    const outcome = await handleSubscriptionChange(
      { subscribe, fallbackKey: null, clients: clientsOf([page]) },
      undefined,
    )
    expect(outcome).toBe('no_key')
    expect(subscribe).not.toHaveBeenCalled()
    expect(page.postMessage).toHaveBeenCalledWith({ type: SW_MESSAGE_SUBSCRIPTION_CHANGED, resubscribed: false })
  })

  it('reports a failed subscribe instead of throwing', async () => {
    const subscribe = vi.fn().mockRejectedValue(new Error('denied'))
    await expect(handleSubscriptionChange({ subscribe, fallbackKey: key, clients: clientsOf([]) }, null)).resolves.toBe(
      'failed',
    )
  })
})
