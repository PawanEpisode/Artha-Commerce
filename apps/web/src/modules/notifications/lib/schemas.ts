import { z } from 'zod'

/** Shapes of the notifications API (PRD 9.2) checked at the edge: a contract drift fails loudly in one place. */

export const CHANNELS = ['push', 'email', 'inbox'] as const
export const channelSchema = z.enum(CHANNELS)
export type Channel = z.infer<typeof channelSchema>

export const permissionStateSchema = z.enum([
  'not_asked',
  'pre_prompt_shown',
  'granted',
  'denied',
  'dismissed',
  'skipped_install',
  'unsupported',
])
export type PermissionState = z.infer<typeof permissionStateSchema>

export const permissionSourceSchema = z.enum(['onboarding', 'followup', 'settings'])
export type PermissionSource = z.infer<typeof permissionSourceSchema>

export const TONES = ['calm', 'driven', 'celebratory'] as const
export const toneSchema = z.enum(TONES)
export type Tone = z.infer<typeof toneSchema>

/** `HH:MM`, 24 hour, as the API reads and writes it. */
export const timeSchema = z.string().regex(/^([01]\d|2[0-3]):[0-5]\d$/)

export const settingsSchema = z.object({
  push_master: z.boolean(),
  timezone: z.string(),
  quiet_enabled: z.boolean(),
  quiet_start: timeSchema,
  quiet_end: timeSchema,
  nudge_enabled: z.boolean(),
  nudge_time: timeSchema,
  nudge_tone: toneSchema,
  permission_state: permissionStateSchema,
  permission_decided: z.boolean(),
  permission_ask_count: z.number().int(),
  last_asked_at: z.string().nullable(),
  /** The server says a follow-up ask may be shown now (spacing and cap are its rules, W2.5b). */
  followup_due: z.boolean().default(false),
})
export type NotificationSettings = z.infer<typeof settingsSchema>

/** What a student can change (PUT is a partial update, so each control saves on its own). */
export type SettingsPatch = Partial<
  Pick<
    NotificationSettings,
    | 'push_master'
    | 'timezone'
    | 'quiet_enabled'
    | 'quiet_start'
    | 'quiet_end'
    | 'nudge_enabled'
    | 'nudge_time'
    | 'nudge_tone'
  >
>

export const categorySchema = z.object({
  key: z.string(),
  label: z.string(),
  description: z.string(),
  channels: z.object({ push: z.boolean(), email: z.boolean(), inbox: z.boolean() }),
})
export type NotificationCategory = z.infer<typeof categorySchema>

export const categoriesResponseSchema = z.object({ categories: z.array(categorySchema) })

export interface PreferenceChange {
  category: string
  channel: Channel
  enabled: boolean
}

export const deviceSchema = z.object({
  id: z.string(),
  label: z.string().default(''),
  platform: z.string().default('other'),
  browser: z.string().default('other'),
  display_mode: z.string().default('browser'),
  last_seen_at: z.string().nullable().optional(),
})
export type NotificationDevice = z.infer<typeof deviceSchema>

/** The list may arrive bare or wrapped (`{devices}` like `{categories}`, or a paginated `{results}`). All are read. */
export const devicesResponseSchema = z
  .union([
    z.array(deviceSchema),
    z.object({ devices: z.array(deviceSchema) }),
    z.object({ results: z.array(deviceSchema) }),
  ])
  .transform((value) => (Array.isArray(value) ? value : 'devices' in value ? value.devices : value.results))

export const deviceIdResponseSchema = z.object({ device_id: z.string().min(1) })

/** Body of `POST devices/`. The endpoint and keys are secrets: they go to the API and nowhere else. */
export interface DeviceRegistration {
  endpoint: string
  keys: { p256dh: string; auth: string }
  platform: string
  browser: string
  display_mode: string
  sw_version: string
  label?: string
}

/** `POST inbox/{id}/click/` may say what was clicked; every field is optional. */
export const clickResponseSchema = z.object({
  category: z.string().optional(),
  seconds_since_sent: z.number().optional(),
})
export type ClickInfo = z.infer<typeof clickResponseSchema>

export const inboxItemSchema = z.object({
  id: z.string(),
  category: z.string(),
  category_label: z.string(),
  title: z.string(),
  body: z.string(),
  /** A relative path the API checked against its allow-list; the page checks it again before following it. */
  deep_link: z.string(),
  read: z.boolean(),
  created_at: z.string(),
})
export type InboxItem = z.infer<typeof inboxItemSchema>

export const inboxPageSchema = z.object({
  results: z.array(inboxItemSchema),
  next_cursor: z.string().nullable(),
  unread_count: z.number().int().nonnegative(),
})
export type InboxPage = z.infer<typeof inboxPageSchema>

export const inboxReadResponseSchema = z.object({ unread_count: z.number().int().nonnegative() })

/** What "mark read" covers: some items by id, or everything. */
export type InboxReadTarget = { ids: readonly string[] } | { all: true }

/** The day's thought (`GET /notifications/thought/today/`): one line, or null when there is nothing to show. */
export const thoughtSchema = z.object({
  id: z.string(),
  body: z.string(),
  attribution: z.string().nullable(),
  shown_on: z.string(),
})
export type DailyThought = z.infer<typeof thoughtSchema>

export const thoughtResponseSchema = z.object({ thought: thoughtSchema.nullable() })

/** What an unsubscribe link is for (`GET`) or just did (`POST`): `/notifications/unsubscribe/`. */
export const unsubscribeSchema = z.object({
  category: z.string(),
  label: z.string(),
  unsubscribed: z.boolean(),
})
export type UnsubscribeResult = z.infer<typeof unsubscribeSchema>

/** `GET` and `POST digest/` (W3.7, FR-N34): whether to offer the digest, whether it is on, and its time. */
export const digestSchema = z.object({ offer: z.boolean(), enabled: z.boolean(), time: timeSchema })
export type DigestState = z.infer<typeof digestSchema>

/** `seen`: the offer was shown. `stop`: back to separate alerts. */
export const DIGEST_ANSWERS = ['seen', 'accept', 'decline', 'stop'] as const
export type DigestAnswer = (typeof DIGEST_ANSWERS)[number]
