import { beforeEach, describe, expect, it, vi } from 'vitest'

const track = vi.hoisted(() => vi.fn())
vi.mock('~/modules/observability', () => ({ track }))
vi.mock('./browser', () => ({
  readEnvironment: () => ({ platform: 'windows', displayMode: 'standalone', browser: 'chrome' }),
}))

import { hasInstallPrompt, listenForInstall, promptInstall, resetInstallPrompt } from './installPrompt'

function installEvent(outcome: 'accepted' | 'dismissed' = 'accepted') {
  const event = new Event('beforeinstallprompt', { cancelable: true })
  return Object.assign(event, {
    prompt: vi.fn().mockResolvedValue(undefined),
    userChoice: Promise.resolve({ outcome }),
  })
}

beforeEach(() => {
  resetInstallPrompt()
  track.mockClear()
})

describe('install prompt capture', () => {
  it('keeps the browser’s event for the offer button and stops the browser’s own bar', () => {
    listenForInstall()
    const event = installEvent()
    window.dispatchEvent(event)
    expect(event.defaultPrevented).toBe(true)
    expect(hasInstallPrompt()).toBe(true)
  })

  it('listens only once, however often it is asked to', async () => {
    listenForInstall()
    listenForInstall()
    window.dispatchEvent(installEvent())
    const result = await promptInstall()
    expect(result).toBe('accepted')
  })

  it('shows the dialog from the click and reports the browser’s answer; the event works once', async () => {
    listenForInstall()
    const event = installEvent('dismissed')
    window.dispatchEvent(event)
    expect(await promptInstall()).toBe('dismissed')
    expect(event.prompt).toHaveBeenCalledOnce()
    expect(hasInstallPrompt()).toBe(false)
    expect(await promptInstall()).toBe('unavailable')
  })

  it('reports installed once when the app is installed, and forgets the event', () => {
    listenForInstall()
    window.dispatchEvent(installEvent())
    window.dispatchEvent(new Event('appinstalled'))
    expect(hasInstallPrompt()).toBe(false)
    expect(track).toHaveBeenCalledWith('pwa_install_result', expect.objectContaining({ result: 'installed' }))
    expect(track).toHaveBeenCalledTimes(1)
  })
})
