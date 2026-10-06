import { describe, expect, it } from 'vitest'

import { applySettingsPatch, channelValue, mergeSavedSettings, setChannel, snapshotFields } from './optimistic'
import type { NotificationCategory, NotificationSettings } from './schemas'

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
  followup_due: false,
}
const categories: NotificationCategory[] = [
  { key: 'timer', label: 'Timer', description: '', channels: { push: true, email: false, inbox: true } },
  { key: 'tracker', label: 'Tracker', description: '', channels: { push: true, email: false, inbox: true } },
]

describe('settings merges', () => {
  it('applies a patch without touching other fields', () => {
    expect(applySettingsPatch(settings, { push_master: false })).toEqual({ ...settings, push_master: false })
  })

  it('snapshots only the fields a patch changes', () => {
    expect(snapshotFields(settings, { quiet_enabled: false, nudge_time: '09:00' })).toEqual({
      quiet_enabled: true,
      nudge_time: '10:00',
    })
  })

  it('takes only the patched fields and the server-owned ones from an answer', () => {
    // The user flipped quiet hours (saved) and then, before that answer came back, changed the timezone.
    const current = { ...settings, quiet_enabled: false, timezone: 'Asia/Dubai' }
    const saved = { ...settings, quiet_enabled: false, timezone: 'Asia/Kolkata', permission_state: 'granted' as const }
    const merged = mergeSavedSettings(current, saved, { quiet_enabled: false })
    expect(merged.quiet_enabled).toBe(false)
    expect(merged.timezone).toBe('Asia/Dubai')
    expect(merged.permission_state).toBe('granted')
  })
})

describe('category merges', () => {
  it('sets one channel of one category', () => {
    const next = setChannel(categories, { category: 'timer', channel: 'push', enabled: false })
    expect(channelValue(next, { category: 'timer', channel: 'push' })).toBe(false)
    expect(channelValue(next, { category: 'timer', channel: 'inbox' })).toBe(true)
    expect(channelValue(next, { category: 'tracker', channel: 'push' })).toBe(true)
    expect(channelValue(categories, { category: 'timer', channel: 'push' })).toBe(true)
  })

  it('is undefined for an unknown category', () => {
    expect(channelValue(categories, { category: 'nope', channel: 'push' })).toBeUndefined()
    expect(setChannel(categories, { category: 'nope', channel: 'push', enabled: false })).toEqual(categories)
  })
})
