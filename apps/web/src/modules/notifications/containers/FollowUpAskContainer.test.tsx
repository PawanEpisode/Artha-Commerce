import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const state = vi.hoisted(() => ({
  flag: true,
  view: { kind: 'ready' } as { kind: string },
  enable: vi.fn(),
  refresh: vi.fn(),
  track: vi.fn(),
  api: { getSettings: vi.fn(), postPermissionState: vi.fn(), listDevices: vi.fn() },
}))

vi.mock('~/modules/observability', () => ({ track: state.track, useFeatureFlag: () => state.flag }))
vi.mock('../lib/api', async (original) => ({ ...(await original<Record<string, unknown>>()), ...state.api }))
vi.mock('../hooks/usePushCapability', () => ({
  usePushCapability: () => ({
    environment: {
      platform: 'windows',
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

import type { NotificationSettings } from '../lib/schemas'
import { FollowUpAskContainer } from './FollowUpAskContainer'

const settings = (over: Partial<NotificationSettings> = {}): NotificationSettings => ({
  push_master: true,
  timezone: 'Asia/Kolkata',
  quiet_enabled: true,
  quiet_start: '22:00',
  quiet_end: '07:00',
  nudge_enabled: true,
  nudge_time: '10:00',
  nudge_tone: 'calm',
  permission_state: 'dismissed',
  permission_decided: true,
  permission_ask_count: 1,
  last_asked_at: null,
  followup_due: true,
  ...over,
})

function setup(roundsFinished: number) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
  const ui = (n: number) => (
    <QueryClientProvider client={client}>
      <FollowUpAskContainer roundsFinished={n} />
    </QueryClientProvider>
  )
  const view = render(ui(roundsFinished))
  return { rerender: (n: number) => view.rerender(ui(n)) }
}

const recorded = () => state.api.postPermissionState.mock.calls.map(([s, src]) => `${s}:${src}`)

beforeEach(() => {
  vi.clearAllMocks()
  state.flag = true
  state.view = { kind: 'ready' }
  state.api.getSettings.mockResolvedValue(settings())
  state.api.postPermissionState.mockResolvedValue(settings())
  state.api.listDevices.mockResolvedValue([])
  state.refresh.mockResolvedValue(undefined)
})

describe('FollowUpAskContainer (W2.5b)', () => {
  it('shows nothing until a round has finished on this visit', async () => {
    const { rerender } = setup(0)
    await waitFor(() => expect(state.api.getSettings).toHaveBeenCalled())
    expect(screen.queryByRole('heading', { name: /next round end/ })).toBeNull()
    rerender(1)
    expect(await screen.findByRole('heading', { name: 'Want to hear the next round end?' })).toBeInTheDocument()
  })

  it('is an inline card, not a modal, and counts as one ask (source followup) even across re-renders', async () => {
    const { rerender } = setup(1)
    expect(await screen.findByRole('region', { name: 'Want to hear the next round end?' })).toBeInTheDocument()
    expect(screen.queryByRole('dialog')).toBeNull()
    rerender(2)
    await waitFor(() => expect(recorded()).toEqual(['pre_prompt_shown:followup']))
  })

  it('stays when the refetch says it is no longer due (it was just counted)', async () => {
    setup(1)
    await screen.findByRole('heading', { name: 'Want to hear the next round end?' })
    state.api.getSettings.mockResolvedValue(settings({ followup_due: false }))
    await waitFor(() => expect(state.api.getSettings.mock.calls.length).toBeGreaterThan(1))
    expect(screen.getByRole('heading', { name: 'Want to hear the next round end?' })).toBeInTheDocument()
  })

  it.each(['not due', 'blocked', 'flag off'])('stays away when %s', async (reason) => {
    if (reason === 'not due') state.api.getSettings.mockResolvedValue(settings({ followup_due: false }))
    if (reason === 'blocked') state.view = { kind: 'blocked' }
    if (reason === 'flag off') state.flag = false
    setup(1)
    await waitFor(() => expect(state.api.getSettings).toHaveBeenCalled())
    await new Promise((r) => setTimeout(r, 20))
    expect(screen.queryByRole('heading', { name: 'Want to hear the next round end?' })).toBeNull()
    expect(recorded()).toEqual([])
  })

  it('Turn on alerts: enables with the followup source, says so politely, and Close puts it away', async () => {
    state.enable.mockResolvedValue({ status: 'enabled', deviceId: 'd1' })
    setup(1)
    await userEvent.click(await screen.findByRole('button', { name: /Turn on alerts/ }))
    expect(state.enable).toHaveBeenCalledTimes(1)
    expect(await screen.findByRole('heading', { name: 'Alerts' })).toHaveFocus()
    expect(screen.getAllByRole('status').some((el) => el.textContent === 'Alerts are on for this device.')).toBe(true)
    await userEvent.click(screen.getByRole('button', { name: 'Close' }))
    expect(screen.queryByRole('heading', { name: 'Alerts' })).toBeNull()
  })

  it('Not now: records the answer (followup) and goes away', async () => {
    setup(1)
    await userEvent.click(await screen.findByRole('button', { name: 'Not now' }))
    await waitFor(() => expect(recorded()).toEqual(['pre_prompt_shown:followup', 'dismissed:followup']))
    expect(screen.queryByRole('heading', { name: 'Want to hear the next round end?' })).toBeNull()
  })

  it('both buttons are reachable by keyboard', async () => {
    setup(1)
    await screen.findByRole('heading', { name: 'Want to hear the next round end?' })
    await userEvent.tab()
    expect(screen.getByRole('button', { name: /Turn on alerts/ })).toHaveFocus()
    await userEvent.tab()
    expect(screen.getByRole('button', { name: 'Not now' })).toHaveFocus()
  })
})
