import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const state = vi.hoisted(() => ({
  flag: true,
  track: vi.fn(),
  enable: vi.fn(),
  refresh: vi.fn(),
  view: { kind: 'ready' } as { kind: string; app?: string },
  api: {
    getSettings: vi.fn(),
    putSettings: vi.fn(),
    getCategories: vi.fn(),
    putPreferences: vi.fn(),
    listDevices: vi.fn(),
    removeDevice: vi.fn(),
    sendTestPush: vi.fn(),
  },
}))

vi.mock('~/modules/observability', () => ({ track: state.track, useFeatureFlag: () => state.flag }))
vi.mock('../lib/api', async (original) => ({ ...(await original<Record<string, unknown>>()), ...state.api }))
vi.mock('../hooks/usePushCapability', () => ({
  usePushCapability: () => ({
    environment: {
      platform: 'android',
      browser: 'chrome',
      displayMode: 'browser',
      inAppBrowser: null,
      support: 'supported',
      label: 'Chrome on Android',
    },
    permission: 'default',
    subscribed: false,
    vapidConfigured: true,
    view: state.view,
    refresh: state.refresh,
  }),
}))
vi.mock('../hooks/usePushEnable', () => ({ usePushEnable: () => ({ enable: state.enable, busy: false }) }))

import { ApiError } from '~/lib/api'

import type { NotificationCategory, NotificationDevice, NotificationSettings } from '../lib/schemas'
import { NotificationSettingsContainer } from './NotificationSettingsContainer'

const settings: NotificationSettings = {
  push_master: true,
  timezone: 'Asia/Kolkata',
  quiet_enabled: true,
  quiet_start: '22:00',
  quiet_end: '07:00',
  nudge_enabled: true,
  nudge_time: '10:00',
  nudge_tone: 'calm',
  permission_state: 'not_asked',
  permission_decided: false,
  permission_ask_count: 0,
  last_asked_at: null,
}
const categories: NotificationCategory[] = [
  {
    key: 'timer',
    label: 'Timer alerts',
    description: 'When a focus round or break ends.',
    channels: { push: true, email: false, inbox: true },
  },
  {
    key: 'tracker',
    label: 'Study tracker',
    description: 'Stopwatch, goal and streak.',
    channels: { push: true, email: false, inbox: true },
  },
]
const device: NotificationDevice = {
  id: 'd1',
  label: 'Chrome on Android',
  platform: 'android',
  browser: 'chrome',
  display_mode: 'browser',
  last_seen_at: new Date().toISOString(),
}
const apiError = (status: number, code?: string, retryAfter?: number) => {
  const error = new ApiError(status, 'x', code ? { error: { code } } : undefined)
  if (retryAfter !== undefined) error.retryAfter = retryAfter
  return error
}

function renderScreen() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <NotificationSettingsContainer />
    </QueryClientProvider>,
  )
}

beforeEach(() => {
  state.flag = true
  state.view = { kind: 'ready' }
  state.track.mockClear()
  state.enable.mockReset()
  state.refresh.mockReset().mockResolvedValue(undefined)
  state.api.getSettings.mockReset().mockResolvedValue(settings)
  state.api.putSettings.mockReset().mockImplementation(async (patch: object) => ({ ...settings, ...patch }))
  state.api.getCategories.mockReset().mockResolvedValue(categories)
  // Answers like the API: the whole catalogue with the requested change applied.
  state.api.putPreferences
    .mockReset()
    .mockImplementation(
      async (changes: { category: string; channel: 'push' | 'email' | 'inbox'; enabled: boolean }[]) =>
        categories.map((c) => ({
          ...c,
          channels: {
            ...c.channels,
            ...Object.fromEntries(changes.filter((x) => x.category === c.key).map((x) => [x.channel, x.enabled])),
          },
        })),
    )
  state.api.listDevices.mockReset().mockResolvedValue([device])
  state.api.removeDevice.mockReset().mockResolvedValue(undefined)
  state.api.sendTestPush.mockReset().mockResolvedValue(undefined)
  window.localStorage.clear()
})

describe('loading, error and off states', () => {
  it('shows one h1 and a polite loading message while settings load', async () => {
    state.api.getSettings.mockReturnValue(new Promise(() => undefined))
    renderScreen()
    expect(screen.getAllByRole('heading', { level: 1 })).toHaveLength(1)
    expect(screen.getByRole('status')).toHaveTextContent('Loading your notification settings')
  })

  it('offers a retry when settings fail to load, and recovers', async () => {
    state.api.getSettings.mockRejectedValueOnce(apiError(500))
    renderScreen()
    expect(await screen.findByRole('alert')).toHaveTextContent('could not load')
    await userEvent.click(screen.getByRole('button', { name: 'Try again' }))
    expect(await screen.findByRole('switch', { name: 'Send alerts to my devices' })).toBeInTheDocument()
  })

  it('says it is not available yet when the server switch is off, and still has its h1', async () => {
    state.api.getSettings.mockRejectedValue(apiError(403, 'notifications_disabled'))
    renderScreen()
    expect(await screen.findByText('Notifications are not available yet')).toBeInTheDocument()
    expect(screen.getAllByRole('heading', { level: 1 })).toHaveLength(1)
    expect(screen.queryByRole('switch')).not.toBeInTheDocument()
  })

  it('says the same when the notifications_ui flag is off', async () => {
    state.flag = false
    renderScreen()
    expect(await screen.findByText('Notifications are not available yet')).toBeInTheDocument()
  })
})

describe('the settings screen', () => {
  it('shows every section with a single h1', async () => {
    renderScreen()
    await screen.findByRole('switch', { name: 'Send alerts to my devices' })
    expect(screen.getAllByRole('heading', { level: 1 })).toHaveLength(1)
    for (const name of ['This device', 'Alerts', 'What to tell me about', 'When', 'Your devices']) {
      expect(screen.getByRole('heading', { level: 2, name })).toBeInTheDocument()
    }
    expect(await screen.findByRole('switch', { name: 'Timer alerts, Push' })).toBeChecked()
    expect(await screen.findByText('Chrome on Android')).toBeInTheDocument()
  })

  it('says where each state stands for this device', async () => {
    state.view = { kind: 'blocked' }
    renderScreen()
    expect(await screen.findByText(/blocked for this site/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Check again/ })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Turn on alerts/ })).not.toBeInTheDocument()
  })

  it('turns alerts on from the card and reloads what changed', async () => {
    state.enable.mockResolvedValue({ status: 'enabled', deviceId: 'd1' })
    renderScreen()
    await userEvent.click(await screen.findByRole('button', { name: /Turn on alerts on this device/ }))
    await waitFor(() => expect(state.enable).toHaveBeenCalledTimes(1))
    await waitFor(() => expect(state.refresh).toHaveBeenCalled())
    await waitFor(() => expect(state.api.listDevices.mock.calls.length).toBeGreaterThan(1))
  })
})

describe('switches save independently', () => {
  it('saves only the master switch when it is flipped', async () => {
    renderScreen()
    await userEvent.click(await screen.findByRole('switch', { name: 'Send alerts to my devices' }))
    await waitFor(() => expect(state.api.putSettings).toHaveBeenCalledTimes(1))
    expect(state.api.putSettings).toHaveBeenCalledWith({ push_master: false })
    expect(state.api.putPreferences).not.toHaveBeenCalled()
    expect(await screen.findByText(/Push alerts are paused/)).toBeInTheDocument()
  })

  it('saves one category and channel per request', async () => {
    renderScreen()
    await userEvent.click(await screen.findByRole('switch', { name: 'Study tracker, Push' }))
    await waitFor(() => expect(state.api.putPreferences).toHaveBeenCalledTimes(1))
    expect(state.api.putPreferences).toHaveBeenCalledWith([{ category: 'tracker', channel: 'push', enabled: false }])
    expect(state.api.putSettings).not.toHaveBeenCalled()
    expect(screen.getByRole('switch', { name: 'Timer alerts, Push' })).toBeChecked()
  })

  it('sends the notification_pref_changed event once per change, with no personal data', async () => {
    renderScreen()
    await userEvent.click(await screen.findByRole('switch', { name: 'Timer alerts, Inbox' }))
    await waitFor(() => expect(state.track).toHaveBeenCalledTimes(1))
    expect(state.track).toHaveBeenCalledWith('notification_pref_changed', {
      category: 'timer',
      channel: 'inbox',
      enabled: false,
    })
  })

  it('puts back only the switch whose save failed', async () => {
    state.api.putPreferences.mockRejectedValueOnce(apiError(500))
    renderScreen()
    const master = await screen.findByRole('switch', { name: 'Send alerts to my devices' })
    await userEvent.click(master)
    await userEvent.click(screen.getByRole('switch', { name: 'Timer alerts, Push' }))
    await waitFor(() => expect(screen.getByRole('switch', { name: 'Timer alerts, Push' })).toBeChecked())
    expect(master).not.toBeChecked()
    expect(state.track).not.toHaveBeenCalled()
  })

  it('saves quiet hours on their own', async () => {
    renderScreen()
    await userEvent.click(await screen.findByRole('switch', { name: 'Quiet hours' }))
    await waitFor(() => expect(state.api.putSettings).toHaveBeenCalledWith({ quiet_enabled: false }))
    expect(screen.queryByLabelText('Quiet from')).not.toBeInTheDocument()
  })

  it('saves a changed quiet time when the field is left, and refuses equal times', async () => {
    renderScreen()
    const start = await screen.findByLabelText('Quiet from')
    await userEvent.clear(start)
    await userEvent.type(start, '23:00')
    await userEvent.tab()
    await waitFor(() => expect(state.api.putSettings).toHaveBeenCalledWith({ quiet_start: '23:00' }))

    const end = screen.getByLabelText('Quiet until')
    state.api.putSettings.mockClear()
    await userEvent.clear(end)
    await userEvent.type(end, '23:00')
    await userEvent.tab()
    expect(await screen.findByText('Start and end must be different times.')).toBeInTheDocument()
    expect(state.api.putSettings).not.toHaveBeenCalled()
  })
})

describe('devices and the test button', () => {
  it('removes a device by its own name', async () => {
    state.api.removeDevice.mockImplementation(async () => {
      state.api.listDevices.mockResolvedValue([])
    })
    renderScreen()
    await userEvent.click(await screen.findByRole('button', { name: 'Remove Chrome on Android' }))
    await waitFor(() => expect(state.api.removeDevice).toHaveBeenCalledWith('d1'))
    expect(await screen.findByText(/No device yet/)).toBeInTheDocument()
    expect(state.track).toHaveBeenCalledWith('push_device_removed', { platform: 'android' })
  })

  it('says so politely when a test was sent, and reports the event', async () => {
    renderScreen()
    await userEvent.click(await screen.findByRole('button', { name: 'Send me a test' }))
    await waitFor(() => expect(state.api.sendTestPush).toHaveBeenCalledWith('d1'))
    const live = await screen.findByText(/Test sent/)
    expect(live.closest('[aria-live="polite"]')).not.toBeNull()
    expect(state.track).toHaveBeenCalledWith('push_test_requested', { platform: 'android' })
  })

  it('handles a 429 with a calm message, and rests the button', async () => {
    state.api.sendTestPush.mockRejectedValue(apiError(429, 'throttled', 30))
    renderScreen()
    const button = await screen.findByRole('button', { name: 'Send me a test' })
    await userEvent.click(button)
    const message = await screen.findByText(/a lot of tests in a row/)
    expect(message).toHaveTextContent('in 30 seconds')
    expect(message.closest('[aria-live="polite"]')).not.toBeNull()
    expect(screen.getByRole('button', { name: 'Send me a test' })).toBeDisabled()
    expect(state.api.sendTestPush).toHaveBeenCalledTimes(1)
  })

  it('says what to do when the device is gone, and reloads the list', async () => {
    state.api.sendTestPush.mockRejectedValue(apiError(404))
    renderScreen()
    await userEvent.click(await screen.findByRole('button', { name: 'Send me a test' }))
    expect(await screen.findByText(/no longer registered/)).toBeInTheDocument()
    await waitFor(() => expect(state.api.listDevices.mock.calls.length).toBeGreaterThan(1))
  })

  it('explains an empty device list and keeps the test button off', async () => {
    state.api.listDevices.mockResolvedValue([])
    renderScreen()
    expect(await screen.findByText(/No device yet/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Send me a test' })).toBeDisabled()
    expect(screen.getByText(/Turn on alerts on this device first/)).toBeInTheDocument()
  })

  it('shows a retry for the device list on its own, without losing the rest', async () => {
    state.api.listDevices.mockRejectedValueOnce(apiError(500))
    renderScreen()
    const list = await screen.findByText('We could not load your devices.')
    expect(screen.getByRole('switch', { name: 'Send alerts to my devices' })).toBeInTheDocument()
    await userEvent.click(
      within(list.closest('[role="alert"]') as HTMLElement).getByRole('button', { name: 'Try again' }),
    )
    expect(await screen.findByText('Chrome on Android')).toBeInTheDocument()
  })
})
