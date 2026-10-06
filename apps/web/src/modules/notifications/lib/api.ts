import { api, ApiError } from '~/lib/api'

import {
  categoriesResponseSchema,
  type ClickInfo,
  clickResponseSchema,
  deviceIdResponseSchema,
  type DeviceRegistration,
  devicesResponseSchema,
  type InboxPage,
  inboxPageSchema,
  inboxReadResponseSchema,
  type InboxReadTarget,
  type NotificationCategory,
  type NotificationDevice,
  type NotificationSettings,
  type PermissionSource,
  type PermissionState,
  type PreferenceChange,
  type SettingsPatch,
  settingsSchema,
} from './schemas'

const send = <T>(method: string, path: string, body?: unknown) =>
  api<T>(path, { method, ...(body === undefined ? {} : { body: JSON.stringify(body) }) })

const BASE = '/notifications'

export const getSettings = async (): Promise<NotificationSettings> =>
  settingsSchema.parse(await api<unknown>(`${BASE}/settings/`))

export const putSettings = async (patch: SettingsPatch): Promise<NotificationSettings> =>
  settingsSchema.parse(await send<unknown>('PUT', `${BASE}/settings/`, patch))

export const getCategories = async (): Promise<NotificationCategory[]> =>
  categoriesResponseSchema.parse(await api<unknown>(`${BASE}/categories/`)).categories

export const putPreferences = async (changes: readonly PreferenceChange[]): Promise<NotificationCategory[]> =>
  categoriesResponseSchema.parse(await send<unknown>('PUT', `${BASE}/preferences/`, { preferences: changes }))
    .categories

export const postPermissionState = async (
  state: PermissionState,
  source: PermissionSource,
): Promise<NotificationSettings> =>
  settingsSchema.parse(await send<unknown>('POST', `${BASE}/permission-state/`, { state, source }))

/** Registers or refreshes this browser. Idempotent on the endpoint, so repeating it is safe. */
export const registerDevice = async (body: DeviceRegistration): Promise<string> =>
  deviceIdResponseSchema.parse(await send<unknown>('POST', `${BASE}/devices/`, body)).device_id

export const listDevices = async (): Promise<NotificationDevice[]> =>
  devicesResponseSchema.parse(await api<unknown>(`${BASE}/devices/`))

export const removeDevice = (id: string) =>
  api<void>(`${BASE}/devices/${encodeURIComponent(id)}/`, { method: 'DELETE' })

export const sendTestPush = (id: string) =>
  send<unknown>('POST', `${BASE}/devices/${encodeURIComponent(id)}/test/`, {}).then(() => undefined)

/** Tells the API the student opened a notification. The answer is optional detail for analytics; its absence is fine. */
export async function postClick(notificationId: string): Promise<ClickInfo> {
  const result = await send<unknown>('POST', `${BASE}/inbox/${encodeURIComponent(notificationId)}/click/`, {})
  const parsed = clickResponseSchema.safeParse(result ?? {})
  return parsed.success ? parsed.data : {}
}

/** One page of the inbox (newest first, at most the last 50 in all) and the unread count. */
export async function getInbox({ cursor, limit }: { cursor?: string | null; limit?: number } = {}): Promise<InboxPage> {
  const query = new URLSearchParams()
  if (cursor) query.set('cursor', cursor)
  if (limit) query.set('limit', String(limit))
  const suffix = query.size > 0 ? `?${query.toString()}` : ''
  return inboxPageSchema.parse(await api<unknown>(`${BASE}/inbox/${suffix}`))
}

/** Marks some or all inbox items read; answers with the new unread count. */
export async function postInboxRead(target: InboxReadTarget): Promise<number> {
  const body = 'all' in target ? { all: true } : { ids: target.ids }
  return inboxReadResponseSchema.parse(await send<unknown>('POST', `${BASE}/inbox/read/`, body)).unread_count
}

const codeOf = (error: unknown): string | undefined => (error instanceof ApiError ? error.code : undefined)

/** 403 `notifications_disabled`: the environment switch or the `notifications_ui` flag is off on the server. */
export const isNotificationsDisabled = (error: unknown) =>
  error instanceof ApiError && error.status === 403 && codeOf(error) === 'notifications_disabled'

export const isRateLimited = (error: unknown): error is ApiError => error instanceof ApiError && error.status === 429

/** 409 `device_limit`: more than ten active devices. */
export const isDeviceLimit = (error: unknown) =>
  error instanceof ApiError && error.status === 409 && codeOf(error) === 'device_limit'

/** 404: the device is already gone (removed elsewhere or pruned after the push service refused it). */
export const isNotFound = (error: unknown) => error instanceof ApiError && error.status === 404
