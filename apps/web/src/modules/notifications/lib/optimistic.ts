import type { NotificationCategory, NotificationSettings, PreferenceChange, SettingsPatch } from './schemas'

/**
 * Pure merges behind the optimistic saves. Each control saves on its own, so a response only ever replaces the fields
 * its own request changed. A slow answer to an earlier toggle can never undo a later one.
 */

/** Fields only the server changes (they follow a permission decision). Always taken from the latest answer. */
const SERVER_OWNED = ['permission_state', 'permission_decided', 'permission_ask_count', 'last_asked_at'] as const

export const applySettingsPatch = (settings: NotificationSettings, patch: SettingsPatch): NotificationSettings => ({
  ...settings,
  ...patch,
})

/** The current values of exactly the fields `patch` will change, so a failure can put them back. */
export function snapshotFields(settings: NotificationSettings, patch: SettingsPatch): SettingsPatch {
  const before: Record<string, unknown> = {}
  for (const key of Object.keys(patch)) before[key] = settings[key as keyof NotificationSettings]
  return before as SettingsPatch
}

export function mergeSavedSettings(
  current: NotificationSettings,
  saved: NotificationSettings,
  patch: SettingsPatch,
): NotificationSettings {
  const next: Record<string, unknown> = { ...current }
  for (const key of [...Object.keys(patch), ...SERVER_OWNED]) next[key] = saved[key as keyof NotificationSettings]
  return next as unknown as NotificationSettings
}

export const channelValue = (
  categories: readonly NotificationCategory[],
  change: Pick<PreferenceChange, 'category' | 'channel'>,
): boolean | undefined => categories.find((c) => c.key === change.category)?.channels[change.channel]

export const setChannel = (
  categories: readonly NotificationCategory[],
  change: PreferenceChange,
): NotificationCategory[] =>
  categories.map((category) =>
    category.key === change.category
      ? { ...category, channels: { ...category.channels, [change.channel]: change.enabled } }
      : category,
  )
