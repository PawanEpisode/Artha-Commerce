import { beforeEach, describe, expect, it, vi } from 'vitest'

const api = vi.hoisted(() => vi.fn())

vi.mock('~/lib/api', async (original) => ({ ...(await original<Record<string, unknown>>()), api }))

import { ApiError } from '~/lib/api'

import {
  getCategories,
  getSettings,
  isDeviceLimit,
  isNotFound,
  isNotificationsDisabled,
  isRateLimited,
  listDevices,
  postClick,
  postPermissionState,
  putPreferences,
  putSettings,
  registerDevice,
  removeDevice,
  sendTestPush,
} from './api'

const settings = {
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
const category = {
  key: 'timer',
  label: 'Timer alerts',
  description: 'x',
  channels: { push: true, email: false, inbox: true },
}
const device = {
  id: 'd1',
  label: 'Chrome on Android',
  platform: 'android',
  browser: 'chrome',
  display_mode: 'browser',
  last_seen_at: '2026-10-06T10:00:00Z',
}
const err = (status: number, code?: string) => new ApiError(status, 'x', code ? { error: { code } } : undefined)

beforeEach(() => api.mockReset())

describe('settings and preferences', () => {
  it('reads and writes settings under /notifications/settings/', async () => {
    api.mockResolvedValue(settings)
    await expect(getSettings()).resolves.toEqual(settings)
    expect(api).toHaveBeenLastCalledWith('/notifications/settings/')
    await putSettings({ push_master: false })
    expect(api).toHaveBeenLastCalledWith('/notifications/settings/', { method: 'PUT', body: '{"push_master":false}' })
  })

  it('rejects a response that breaks the contract', async () => {
    api.mockResolvedValue({ ...settings, nudge_tone: 'shouty' })
    await expect(getSettings()).rejects.toThrow()
  })

  it('unwraps categories and sends a bulk preference change', async () => {
    api.mockResolvedValue({ categories: [category] })
    await expect(getCategories()).resolves.toEqual([category])
    await putPreferences([{ category: 'timer', channel: 'push', enabled: false }])
    expect(api).toHaveBeenLastCalledWith('/notifications/preferences/', {
      method: 'PUT',
      body: '{"preferences":[{"category":"timer","channel":"push","enabled":false}]}',
    })
  })

  it('records the permission decision with its source', async () => {
    api.mockResolvedValue(settings)
    await postPermissionState('denied', 'settings')
    expect(api).toHaveBeenLastCalledWith('/notifications/permission-state/', {
      method: 'POST',
      body: '{"state":"denied","source":"settings"}',
    })
  })
})

describe('devices', () => {
  it('reads a bare list, a {devices} wrapper and a paginated {results} wrapper', async () => {
    for (const body of [[device], { devices: [device] }, { results: [device] }]) {
      api.mockResolvedValueOnce(body)
      await expect(listDevices()).resolves.toEqual([device])
    }
  })

  it('fills in defaults for a device with missing optional fields', async () => {
    api.mockResolvedValue([{ id: 'd2' }])
    await expect(listDevices()).resolves.toEqual([
      { id: 'd2', label: '', platform: 'other', browser: 'other', display_mode: 'browser' },
    ])
  })

  it('registers with the whole contract and returns only the id', async () => {
    api.mockResolvedValue({ device_id: 'd1' })
    const body = {
      endpoint: 'https://push.example.test/x',
      keys: { p256dh: 'P', auth: 'A' },
      platform: 'android',
      browser: 'chrome',
      display_mode: 'browser',
      sw_version: 'abc1234',
      label: 'Chrome on Android',
    }
    await expect(registerDevice(body)).resolves.toBe('d1')
    expect(api).toHaveBeenLastCalledWith('/notifications/devices/', { method: 'POST', body: JSON.stringify(body) })
  })

  it('removes and tests a device by id, escaping it', async () => {
    api.mockResolvedValue(undefined)
    await removeDevice('d/1')
    expect(api).toHaveBeenLastCalledWith('/notifications/devices/d%2F1/', { method: 'DELETE' })
    await sendTestPush('d1')
    expect(api).toHaveBeenLastCalledWith('/notifications/devices/d1/test/', { method: 'POST', body: '{}' })
  })
})

describe('postClick', () => {
  it('posts to the inbox click endpoint and returns the optional detail', async () => {
    api.mockResolvedValue({ category: 'timer', seconds_since_sent: 12, extra: 1 })
    await expect(postClick('n_1')).resolves.toEqual({ category: 'timer', seconds_since_sent: 12 })
    expect(api).toHaveBeenLastCalledWith('/notifications/inbox/n_1/click/', { method: 'POST', body: '{}' })
  })

  it('accepts an empty answer (204) and an unexpected one', async () => {
    api.mockResolvedValueOnce(undefined)
    await expect(postClick('n_1')).resolves.toEqual({})
    api.mockResolvedValueOnce({ category: 5 })
    await expect(postClick('n_1')).resolves.toEqual({})
  })
})

describe('error helpers', () => {
  it('reads the codes the API uses', () => {
    expect(isNotificationsDisabled(err(403, 'notifications_disabled'))).toBe(true)
    expect(isNotificationsDisabled(err(403, 'feature_disabled'))).toBe(false)
    expect(isNotificationsDisabled(err(500, 'notifications_disabled'))).toBe(false)
    expect(isDeviceLimit(err(409, 'device_limit'))).toBe(true)
    expect(isDeviceLimit(err(409, 'stale_version'))).toBe(false)
    expect(isRateLimited(err(429))).toBe(true)
    expect(isRateLimited(err(400))).toBe(false)
    expect(isNotFound(err(404))).toBe(true)
    expect(isNotFound(new Error('x'))).toBe(false)
  })
})
