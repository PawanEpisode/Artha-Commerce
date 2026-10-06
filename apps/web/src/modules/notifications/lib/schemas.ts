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
