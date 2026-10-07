import { act, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const state = vi.hoisted(() => ({ track: vi.fn(), flag: true, env: {} as Record<string, unknown> }))
vi.mock('~/modules/observability', () => ({ track: state.track, useFeatureFlag: () => state.flag }))
vi.mock('../lib/browser', () => ({ readEnvironment: () => state.env }))

import { listenForInstall, resetInstallPrompt } from '../lib/installPrompt'
import { InstallOfferContainer } from './InstallOfferContainer'

const DAY = 24 * 60 * 60 * 1000
const environment = (patch: Record<string, unknown> = {}) => ({
  platform: 'windows',
  browser: 'chrome',
  displayMode: 'browser',
  inAppBrowser: null,
  ...patch,
})

function fireInstallEvent(outcome: 'accepted' | 'dismissed' = 'accepted') {
  const event = Object.assign(new Event('beforeinstallprompt', { cancelable: true }), {
    prompt: vi.fn().mockResolvedValue(undefined),
    userChoice: Promise.resolve({ outcome }),
  })
  act(() => void window.dispatchEvent(event))
  return event
}

const card = () => screen.queryByRole('region', { name: 'Keep Artha one tap away' })
const results = () => state.track.mock.calls.filter(([name]) => name === 'pwa_install_result')

beforeEach(() => {
  state.flag = true
  state.env = environment()
  state.track.mockClear()
  localStorage.clear()
  resetInstallPrompt()
  listenForInstall()
})

describe('InstallOfferContainer (X-01 W4.5)', () => {
  it('shows after the second finished round on this device, and records that it was offered', async () => {
    localStorage.setItem('artha:install:rounds', '1')
    fireInstallEvent()
    render(<InstallOfferContainer roundsFinished={1} />)
    expect(await screen.findByRole('region', { name: 'Keep Artha one tap away' })).toBeInTheDocument()
    expect(localStorage.getItem('artha:install:rounds')).toBe('2')
    expect(Number(localStorage.getItem('artha:install:offered-at'))).toBeGreaterThan(0)
    expect(results()).toHaveLength(0)
  })

  it('counts each round once, and stays quiet after only the first', async () => {
    fireInstallEvent()
    const view = render(<InstallOfferContainer roundsFinished={1} />)
    await waitFor(() => expect(localStorage.getItem('artha:install:rounds')).toBe('1'))
    view.rerender(<InstallOfferContainer roundsFinished={1} />)
    expect(localStorage.getItem('artha:install:rounds')).toBe('1')
    expect(card()).toBeNull()
    view.rerender(<InstallOfferContainer roundsFinished={2} />)
    expect(await screen.findByRole('region')).toBeInTheDocument()
    expect(localStorage.getItem('artha:install:rounds')).toBe('2')
  })

  it('waits for a round to end on this visit even when the device count is high', () => {
    localStorage.setItem('artha:install:rounds', '9')
    fireInstallEvent()
    render(<InstallOfferContainer roundsFinished={0} />)
    expect(card()).toBeNull()
  })

  it('does not come back within 30 days, and does after', async () => {
    localStorage.setItem('artha:install:rounds', '5')
    localStorage.setItem('artha:install:offered-at', String(Date.now() - 10 * DAY))
    fireInstallEvent()
    const first = render(<InstallOfferContainer roundsFinished={1} />)
    await waitFor(() => expect(localStorage.getItem('artha:install:rounds')).toBe('6'))
    expect(card()).toBeNull()
    first.unmount()
    localStorage.setItem('artha:install:offered-at', String(Date.now() - 31 * DAY))
    render(<InstallOfferContainer roundsFinished={1} />)
    expect(await screen.findByRole('region')).toBeInTheDocument()
  })

  it.each([
    ['inside the installed app', { displayMode: 'standalone' }],
    ['inside another app’s browser', { inAppBrowser: 'WhatsApp' }],
    ['in Firefox, which cannot install', { browser: 'firefox' }],
  ])('never shows %s', async (_why, patch) => {
    state.env = environment(patch)
    localStorage.setItem('artha:install:rounds', '5')
    if (!('browser' in patch)) fireInstallEvent()
    render(<InstallOfferContainer roundsFinished={1} />)
    await waitFor(() => expect(localStorage.getItem('artha:install:rounds')).toBe('6'))
    expect(card()).toBeNull()
  })

  it('shows nothing and records nothing as offered with the floating_timer flag off', async () => {
    state.flag = false
    localStorage.setItem('artha:install:rounds', '5')
    fireInstallEvent()
    render(<InstallOfferContainer roundsFinished={1} />)
    await waitFor(() => expect(localStorage.getItem('artha:install:rounds')).toBe('6'))
    expect(card()).toBeNull()
    expect(localStorage.getItem('artha:install:offered-at')).toBeNull()
  })

  it('Install Artha shows the browser dialog from the click, reports accepted once and closes', async () => {
    localStorage.setItem('artha:install:rounds', '1')
    const event = fireInstallEvent('accepted')
    render(<InstallOfferContainer roundsFinished={1} />)
    await userEvent.click(await screen.findByRole('button', { name: /Install Artha/ }))
    expect(event.prompt).toHaveBeenCalledOnce()
    await waitFor(() => expect(card()).toBeNull())
    expect(results()).toEqual([
      ['pwa_install_result', expect.objectContaining({ result: 'accepted', kind: 'prompt', platform: 'windows' })],
    ])
  })

  it('reports dismissed when the student says no in the browser’s dialog', async () => {
    localStorage.setItem('artha:install:rounds', '1')
    fireInstallEvent('dismissed')
    render(<InstallOfferContainer roundsFinished={1} />)
    await userEvent.click(await screen.findByRole('button', { name: /Install Artha/ }))
    await waitFor(() => expect(card()).toBeNull())
    expect(results()).toEqual([['pwa_install_result', expect.objectContaining({ result: 'dismissed' })]])
  })

  it('Not now closes it without reporting a result, and it is not shown again this visit', async () => {
    localStorage.setItem('artha:install:rounds', '1')
    fireInstallEvent()
    const view = render(<InstallOfferContainer roundsFinished={1} />)
    await userEvent.click(await screen.findByRole('button', { name: 'Not now' }))
    expect(card()).toBeNull()
    view.rerender(<InstallOfferContainer roundsFinished={2} />)
    expect(card()).toBeNull()
    expect(results()).toHaveLength(0)
  })

  it('iPhone Safari: shows the steps, reports guide_shown once, and Got it closes it', async () => {
    state.env = environment({ platform: 'ios', browser: 'safari' })
    localStorage.setItem('artha:install:rounds', '1')
    const view = render(<InstallOfferContainer roundsFinished={1} />)
    expect(await screen.findByText('Add to Home Screen')).toBeInTheDocument()
    view.rerender(<InstallOfferContainer roundsFinished={1} />)
    expect(results()).toEqual([
      ['pwa_install_result', expect.objectContaining({ result: 'guide_shown', kind: 'ios_steps' })],
    ])
    await userEvent.click(screen.getByRole('button', { name: 'Got it' }))
    expect(card()).toBeNull()
  })

  it('Safari on a Mac: one line, File then Add to Dock', async () => {
    state.env = environment({ platform: 'macos', browser: 'safari' })
    localStorage.setItem('artha:install:rounds', '1')
    render(<InstallOfferContainer roundsFinished={1} />)
    expect(await screen.findByText('Add to Dock')).toBeInTheDocument()
    expect(results()).toEqual([
      ['pwa_install_result', expect.objectContaining({ result: 'guide_shown', kind: 'mac_safari' })],
    ])
  })
})
