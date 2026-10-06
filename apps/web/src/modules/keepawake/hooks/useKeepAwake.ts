import { useQuery } from '@tanstack/react-query'

import { api } from '~/lib/api'
import { useFeatureFlag } from '~/modules/observability'

import { keepAwakeKeys } from '../lib/keys'
import { type KeepAwakeActivity, type KeepAwakeSettings, type KeepAwakeStatus, wantsWakeLock } from '../lib/wakeLock'
import { useWakeLock } from './useWakeLock'

/** The two switches live with the focus settings (`GET /focus/settings/`); this reads only those two fields. */
const getKeepAwakeSettings = async (): Promise<KeepAwakeSettings> => {
  const s = await api<Partial<KeepAwakeSettings>>('/focus/settings/')
  return { keep_awake: s.keep_awake ?? true, keep_awake_in_breaks: s.keep_awake_in_breaks ?? false }
}

/**
 * Keeps the screen on while a timer runs, for any timer (the Pomodoro and the stopwatch share it). Pass what the
 * timer is doing, or null when there is none. `settings` is optional: a page that already has the focus settings
 * hands them in; otherwise they are read here, and only while a timer exists. Until they are known, and if they
 * cannot be read, nothing is held. The PostHog flag `keep_awake` (fails open) switches the whole thing off.
 */
export function useKeepAwake(activity: KeepAwakeActivity | null, settings?: KeepAwakeSettings): KeepAwakeStatus {
  const flagOn = useFeatureFlag('keep_awake')
  const own = useQuery({
    queryKey: keepAwakeKeys.settings,
    queryFn: getKeepAwakeSettings,
    enabled: activity !== null && settings === undefined && flagOn,
    staleTime: 60_000,
  })
  const known = settings ?? own.data
  return useWakeLock(flagOn && wantsWakeLock(activity, known))
}
