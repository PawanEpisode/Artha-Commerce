import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const state = vi.hoisted(() => ({
  track: vi.fn(),
  enable: vi.fn(),
  refresh: vi.fn(),
  copy: vi.fn(),
  view: { kind: 'ready' } as { kind: string; app?: string },
  platform: 'android',
  api: {
    getSettings: vi.fn(),
    listDevices: vi.fn(),
    sendTestPush: vi.fn(),
    postPermissionState: vi.fn(),
  },
}))

vi.mock('~/modules/observability', () => ({ track: state.track, useFeatureFlag: () => true }))
vi.mock('../lib/api', async (original) => ({ ...(await original<Record<string, unknown>>()), ...state.api }))
vi.mock('../lib/clipboard', () => ({ copyText: state.copy }))
vi.mock('../hooks/usePushCapability', () => ({
  usePushCapability: () => ({
    environment: {
      platform: state.platform,
      browser: 'chrome',
      displayMode: 'browser',
      inAppBrowser: null,
      support: 'supported',
      label: 'Chrome',
    },
    permission: 'default',
    subscribed: false,
    vapidConfigured: true,
    view: state.view,
    refresh: state.refresh,
  }),
}))
vi.mock('../hooks/usePushEnable', () => ({ usePushEnable: () => ({ enable: state.enable, busy: false }) }))
vi.mock('../hooks/useRegistrationRefresh', () => ({ useRegistrationRefresh: () => undefined }))

import { ApiError } from '~/lib/api'

import type { NotificationSettings } from '../lib/schemas'
import { AlertsStepContainer } from './AlertsStepContainer'

const settings = (permission_state: NotificationSettings['permission_state'] = 'not_asked'): NotificationSettings => ({
  push_master: true,
  timezone: 'Asia/Kolkata',
  quiet_enabled: true,
  quiet_start: '22:00',
  quiet_end: '07:00',
  nudge_enabled: true,
  nudge_time: '10:00',
  nudge_tone: 'calm',
  permission_state,
  permission_decided: permission_state !== 'not_asked' && permission_state !== 'pre_prompt_shown',
  permission_ask_count: 0,
  last_asked_at: null,
  followup_due: false,
})
const device = {
  id: 'd1',
  label: 'Chrome on Android',
  platform: 'android',
  browser: 'chrome',
  display_mode: 'browser',
  last_seen_at: null,
}

function setup(view: { kind: string; app?: string } = { kind: 'ready' }, serverState = settings()) {
  state.view = view
  state.api.getSettings.mockResolvedValue(serverState)
  const onFinish = vi.fn().mockResolvedValue(undefined)
  const onSkip = vi.fn().mockResolvedValue(undefined)
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
  render(
    <QueryClientProvider client={client}>
      <AlertsStepContainer onFinish={onFinish} onSkip={onSkip} />
    </QueryClientProvider>,
  )
  return { onFinish, onSkip }
}

const recorded = () => state.api.postPermissionState.mock.calls.map(([s, src]) => `${s}:${src}`)
const eventNames = () => state.track.mock.calls.map(([name]) => name)

beforeEach(() => {
  vi.clearAllMocks()
  state.platform = 'android'
  state.api.listDevices.mockResolvedValue([])
  state.api.postPermissionState.mockImplementation(async (s: string) => settings(s as never))
  state.api.sendTestPush.mockResolvedValue(undefined)
  state.refresh.mockResolvedValue(undefined)
  state.copy.mockResolvedValue(true)
})

describe('AlertsStepContainer: pre-prompt (browser permission undecided)', () => {
  it('is a page with the purpose and an example, not a modal, and counts as one ask', async () => {
    setup()
    expect(await screen.findByRole('heading', { level: 2, name: 'Hear when your round ends' })).toBeInTheDocument()
    expect(screen.getByText(/no marketing/i)).toBeInTheDocument()
    expect(screen.getByText(/turn alerts off any time in Settings/i)).toBeInTheDocument()
    expect(screen.queryByRole('dialog')).toBeNull()
    expect(screen.queryByRole('heading', { level: 1 })).toBeNull() // the flow owns the one h1
    await waitFor(() => expect(recorded()).toEqual(['pre_prompt_shown:onboarding']))
  })

  it('does not count a second ask when the server already recorded the pre-prompt', async () => {
    setup({ kind: 'ready' }, settings('pre_prompt_shown'))
    await screen.findByRole('heading', { name: 'Hear when your round ends' })
    expect(recorded()).toEqual([])
  })

  it('reports the screen once', async () => {
    setup()
    await screen.findByRole('heading', { name: 'Hear when your round ends' })
    await waitFor(() => expect(eventNames()).toContain('alerts_step_viewed'))
    expect(state.track).toHaveBeenCalledWith('alerts_step_viewed', {
      branch: 'pre_prompt',
      platform: 'android',
      display_mode: 'browser',
    })
    expect(eventNames().filter((n) => n === 'alerts_step_viewed')).toHaveLength(1)
  })

  it('Allow: subscribes through the onboarding source, shows the granted card and the test button, then finishes granted', async () => {
    state.enable.mockImplementation(async () => {
      state.api.listDevices.mockResolvedValue([device])
      return { status: 'enabled', deviceId: 'd1' }
    })
    const { onFinish } = setup()
    await userEvent.click(await screen.findByRole('button', { name: /Turn on alerts/ }))
    expect(state.enable).toHaveBeenCalledTimes(1)
    expect(await screen.findByRole('heading', { name: 'Alerts are on' })).toHaveFocus()
    expect(screen.getByText('On')).toBeInTheDocument()
    expect(screen.getAllByRole('status').some((el) => el.textContent === 'Alerts are on for this device.')).toBe(true)

    await userEvent.click(screen.getByRole('button', { name: 'Send me a test' }))
    await waitFor(() => expect(state.api.sendTestPush).toHaveBeenCalledWith('d1'))

    await userEvent.click(screen.getByRole('button', { name: 'Continue' }))
    await waitFor(() => expect(onFinish).toHaveBeenCalledWith('granted'))
    expect(recorded()).toContain('granted:onboarding')
    expect(state.track).toHaveBeenCalledWith('alerts_step_completed', {
      result: 'granted',
      platform: 'android',
      display_mode: 'browser',
    })
  })

  it('Block: says so kindly, never shows unblock steps here, and finishes denied', async () => {
    state.enable.mockResolvedValue({ status: 'denied' })
    const { onFinish } = setup()
    await userEvent.click(await screen.findByRole('button', { name: /Turn on alerts/ }))
    expect(await screen.findByRole('heading', { name: 'Alerts are off' })).toHaveFocus()
    expect(screen.queryByText(/lock icon/i)).toBeNull()
    await userEvent.click(screen.getByRole('button', { name: 'Continue' }))
    await waitFor(() => expect(onFinish).toHaveBeenCalledWith('denied'))
    expect(recorded()).toContain('denied:onboarding')
  })

  it('a closed prompt is "dismissed": Continue, or ask again', async () => {
    state.enable.mockResolvedValueOnce({ status: 'dismissed' })
    const { onFinish } = setup()
    await userEvent.click(await screen.findByRole('button', { name: /Turn on alerts/ }))
    expect(await screen.findByRole('heading', { name: 'No problem' })).toBeInTheDocument()
    state.enable.mockResolvedValueOnce({ status: 'enabled', deviceId: 'd1' })
    await userEvent.click(screen.getByRole('button', { name: /Turn on alerts after all/ }))
    expect(await screen.findByRole('heading', { name: 'Alerts are on' })).toBeInTheDocument()
    expect(onFinish).not.toHaveBeenCalled()
  })

  it('Not now: records dismissed and finishes dismissed', async () => {
    const { onFinish } = setup()
    await userEvent.click(await screen.findByRole('button', { name: 'Not now' }))
    await waitFor(() => expect(onFinish).toHaveBeenCalledWith('dismissed'))
    expect(recorded()).toContain('dismissed:onboarding')
    expect(state.enable).not.toHaveBeenCalled()
  })

  it('a registration problem is said in words and the button works again', async () => {
    state.enable.mockResolvedValueOnce({ status: 'error', reason: 'register_failed' })
    setup()
    await userEvent.click(await screen.findByRole('button', { name: /Turn on alerts/ }))
    expect(await screen.findByRole('alert')).toHaveTextContent('We could not turn alerts on')
    expect(screen.getByRole('button', { name: /Turn on alerts/ })).toBeEnabled()
  })

  it('too many devices: the permission is granted, so the step finishes granted', async () => {
    state.enable.mockResolvedValue({ status: 'device_limit' })
    const { onFinish } = setup()
    await userEvent.click(await screen.findByRole('button', { name: /Turn on alerts/ }))
    expect(await screen.findByRole('heading', { name: 'You have too many devices' })).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Continue' }))
    await waitFor(() => expect(onFinish).toHaveBeenCalledWith('granted'))
  })

  it('every action is reachable and usable from the keyboard alone', async () => {
    const { onFinish } = setup()
    await screen.findByRole('heading', { name: 'Hear when your round ends' })
    await userEvent.tab()
    expect(screen.getByRole('button', { name: /Turn on alerts/ })).toHaveFocus()
    await userEvent.tab()
    expect(screen.getByRole('button', { name: 'Not now' })).toHaveFocus()
    await userEvent.keyboard('{Enter}')
    await waitFor(() => expect(onFinish).toHaveBeenCalledWith('dismissed'))
  })

  it('granted in the browser but not registered with us: one tap finishes it, no prompt text', async () => {
    state.enable.mockResolvedValue({ status: 'enabled', deviceId: 'd1' })
    setup({ kind: 'granted_no_device' })
    expect(await screen.findByRole('heading', { name: 'One more tap to finish' })).toBeInTheDocument()
    expect(screen.queryByText(/will ask for permission/)).toBeNull()
    await userEvent.click(screen.getByRole('button', { name: /Set up this device/ }))
    expect(await screen.findByRole('heading', { name: 'Alerts are on' })).toBeInTheDocument()
  })
})

describe('AlertsStepContainer: every other branch of PRD 5.1', () => {
  it('already subscribed: shows alerts are on and finishes granted', async () => {
    state.api.listDevices.mockResolvedValue([device])
    const { onFinish } = setup({ kind: 'active' })
    expect(await screen.findByRole('heading', { name: 'Alerts are on' })).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Continue' }))
    await waitFor(() => expect(onFinish).toHaveBeenCalledWith('granted'))
    expect(recorded()).toEqual(['granted:onboarding'])
  })

  it('blocked on arrival: unblock steps for this browser, Check again, and Skip finishes as blocked (stored as denied)', async () => {
    const { onFinish } = setup({ kind: 'blocked' })
    expect(await screen.findByRole('heading', { name: 'Alerts are blocked for this site' })).toBeInTheDocument()
    expect(screen.getByText(/lock icon/i)).toBeInTheDocument()
    expect(screen.getByText('Blocked')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: /Check again/ }))
    expect(state.refresh).toHaveBeenCalled()
    expect(await screen.findByText(/Still blocked/)).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Skip for now' }))
    await waitFor(() => expect(onFinish).toHaveBeenCalledWith('blocked'))
    expect(recorded()).toEqual(['denied:onboarding'])
    expect(state.track).toHaveBeenCalledWith('alerts_step_completed', expect.objectContaining({ result: 'blocked' }))
  })

  it('iPhone Safari tab: the Home Screen guide, and "Continue without alerts" finishes skipped_install', async () => {
    state.platform = 'ios'
    const { onFinish } = setup({ kind: 'ios_needs_install' })
    expect(await screen.findByRole('heading', { name: 'Add Artha to your Home Screen first' })).toBeInTheDocument()
    expect(screen.getByText(/Add to Home Screen/)).toBeInTheDocument()
    expect(screen.getByText('Install first')).toBeInTheDocument()
    expect(screen.getAllByRole('listitem')).toHaveLength(3)
    await userEvent.click(screen.getByRole('button', { name: 'Continue without alerts' }))
    await waitFor(() => expect(onFinish).toHaveBeenCalledWith('skipped_install'))
    expect(recorded()).toEqual(['skipped_install:onboarding'])
  })

  it('in-app browser: names the app, copies the link, and lets the student carry on', async () => {
    const { onFinish } = setup({ kind: 'in_app_browser', app: 'WhatsApp' })
    expect(await screen.findByRole('heading', { name: 'Open Artha in your browser' })).toBeInTheDocument()
    expect(screen.getByText(/inside WhatsApp/)).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Copy link' }))
    expect(state.copy).toHaveBeenCalledWith(window.location.href)
    await waitFor(() =>
      expect(screen.getAllByRole('status').some((el) => /Link copied/.test(el.textContent ?? ''))).toBe(true),
    )
    await userEvent.click(screen.getByRole('button', { name: 'Continue without alerts' }))
    await waitFor(() => expect(onFinish).toHaveBeenCalledWith('dismissed'))
  })

  it('in-app browser: says plainly when the copy failed', async () => {
    state.copy.mockResolvedValue(false)
    setup({ kind: 'in_app_browser', app: 'Instagram' })
    await userEvent.click(await screen.findByRole('button', { name: 'Copy link' }))
    await waitFor(() =>
      expect(screen.getAllByRole('status').some((el) => /Could not copy/.test(el.textContent ?? ''))).toBe(true),
    )
  })

  it('unsupported: a note, and Continue finishes unsupported', async () => {
    const { onFinish } = setup({ kind: 'unsupported' })
    expect(await screen.findByRole('heading', { name: 'This browser cannot show alerts' })).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Continue' }))
    await waitFor(() => expect(onFinish).toHaveBeenCalledWith('unsupported'))
    expect(recorded()).toEqual(['unsupported:onboarding'])
  })

  it('a build without a push key records nothing and skips the step instead of faking a decision', async () => {
    const { onFinish, onSkip } = setup({ kind: 'not_configured' })
    expect(await screen.findByRole('heading', { name: 'Alerts are not ready yet' })).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Continue' }))
    await waitFor(() => expect(onSkip).toHaveBeenCalledTimes(1))
    expect(onFinish).not.toHaveBeenCalled()
    expect(recorded()).toEqual([])
  })

  it('the server says notifications are off: the step steps aside through skip', async () => {
    state.view = { kind: 'ready' }
    state.api.getSettings.mockRejectedValue(new ApiError(403, 'off', { error: { code: 'notifications_disabled' } }))
    const onSkip = vi.fn().mockResolvedValue(undefined)
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    render(
      <QueryClientProvider client={client}>
        <AlertsStepContainer onFinish={vi.fn()} onSkip={onSkip} />
      </QueryClientProvider>,
    )
    expect(await screen.findByRole('heading', { name: 'Alerts are not ready yet' })).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Continue' }))
    await waitFor(() => expect(onSkip).toHaveBeenCalled())
  })
})

describe('AlertsStepContainer: failures never trap the student', () => {
  it('a failed save is said once and the same button retries', async () => {
    const { onFinish } = setup()
    onFinish.mockRejectedValueOnce(new Error('network')).mockResolvedValueOnce(undefined)
    await userEvent.click(await screen.findByRole('button', { name: 'Not now' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('We could not save that')
    await userEvent.click(screen.getByRole('button', { name: 'Not now' }))
    await waitFor(() => expect(onFinish).toHaveBeenCalledTimes(2))
    expect(eventNames().filter((n) => n === 'alerts_step_completed')).toHaveLength(1)
  })

  it('a failed consent record does not move on without a record', async () => {
    state.api.postPermissionState.mockImplementation(async (s: string) => {
      if (s === 'pre_prompt_shown') return settings('pre_prompt_shown')
      throw new ApiError(500, 'boom')
    })
    const { onFinish } = setup()
    await userEvent.click(await screen.findByRole('button', { name: 'Not now' }))
    expect(await screen.findByRole('alert')).toBeInTheDocument()
    expect(onFinish).not.toHaveBeenCalled()
  })
})
