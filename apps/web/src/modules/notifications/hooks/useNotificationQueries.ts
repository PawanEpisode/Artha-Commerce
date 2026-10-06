import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { notificationAnalytics } from '../lib/analytics'
import { getCategories, getSettings, listDevices, putPreferences, putSettings, removeDevice } from '../lib/api'
import { forgetDeviceId, rememberedDeviceId } from '../lib/deviceMemory'
import { notificationKeys } from '../lib/keys'
import { applySettingsPatch, channelValue, mergeSavedSettings, setChannel, snapshotFields } from '../lib/optimistic'
import { unsubscribeFromPush } from '../lib/push'
import type {
  NotificationCategory,
  NotificationDevice,
  NotificationSettings,
  PreferenceChange,
  SettingsPatch,
} from '../lib/schemas'
import { peekPushBrowser } from '../lib/serviceWorker'

export const useNotificationSettings = () => useQuery({ queryKey: notificationKeys.settings, queryFn: getSettings })

/** Each call saves its own fields and nothing else; see `lib/optimistic.ts` for why answers merge by field. */
export function useSaveNotificationSettings() {
  const qc = useQueryClient()
  const key = notificationKeys.settings
  return useMutation({
    mutationFn: (patch: SettingsPatch) => putSettings(patch),
    onMutate: async (patch) => {
      await qc.cancelQueries({ queryKey: key })
      const current = qc.getQueryData<NotificationSettings>(key)
      qc.setQueryData<NotificationSettings>(key, (old) => (old ? applySettingsPatch(old, patch) : old))
      return { before: current ? snapshotFields(current, patch) : null }
    },
    onError: (_error, _patch, context) => {
      const before = context?.before
      if (before) qc.setQueryData<NotificationSettings>(key, (old) => (old ? applySettingsPatch(old, before) : old))
    },
    onSuccess: (saved, patch) => {
      qc.setQueryData<NotificationSettings>(key, (old) => (old ? mergeSavedSettings(old, saved, patch) : saved))
    },
  })
}

export const useNotificationCategories = () =>
  useQuery({ queryKey: notificationKeys.categories, queryFn: getCategories })

/** One switch (category and channel) per request, so switches save independently. */
export function useSetPreference() {
  const qc = useQueryClient()
  const key = notificationKeys.categories
  return useMutation({
    mutationFn: (change: PreferenceChange) => putPreferences([change]),
    onMutate: async (change) => {
      await qc.cancelQueries({ queryKey: key })
      const previous = channelValue(qc.getQueryData<NotificationCategory[]>(key) ?? [], change)
      qc.setQueryData<NotificationCategory[]>(key, (old) => (old ? setChannel(old, change) : old))
      return { previous }
    },
    onError: (_error, change, context) => {
      if (context?.previous === undefined) return
      const restore = { ...change, enabled: context.previous }
      qc.setQueryData<NotificationCategory[]>(key, (old) => (old ? setChannel(old, restore) : old))
    },
    onSuccess: (saved, change) => {
      const enabled = channelValue(saved, change) ?? change.enabled
      qc.setQueryData<NotificationCategory[]>(key, (old) => (old ? setChannel(old, { ...change, enabled }) : saved))
      notificationAnalytics.prefChanged({ ...change, enabled })
    },
  })
}

export const useDevices = () => useQuery({ queryKey: notificationKeys.devices, queryFn: listDevices })

/**
 * Removes a device. When it is this browser, the local subscription goes too, so the browser stops holding an
 * endpoint nobody can send to. The API call comes first: if it fails nothing local changes.
 */
export function useRemoveDevice() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (device: NotificationDevice) => {
      await removeDevice(device.id)
      if (device.id === rememberedDeviceId()) {
        forgetDeviceId()
        await unsubscribeFromPush(peekPushBrowser).catch(() => false)
      }
      return device
    },
    onSuccess: (device) => {
      qc.setQueryData<NotificationDevice[]>(notificationKeys.devices, (old) => old?.filter((d) => d.id !== device.id))
      notificationAnalytics.deviceRemoved(device.platform)
    },
    onSettled: () => qc.invalidateQueries({ queryKey: notificationKeys.devices }),
  })
}
