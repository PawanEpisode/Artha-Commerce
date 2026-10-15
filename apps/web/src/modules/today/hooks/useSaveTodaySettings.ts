import { toast } from '@artha/design-system'
import { useMutation, useQueryClient } from '@tanstack/react-query'

import { trackToday } from '../lib/analytics'
import { rebuildToday, saveSettings } from '../lib/api'
import { todayKeys } from '../lib/keys'
import { changedKeys } from '../lib/settings'
import type { OpenResult, TodaySettings } from '../lib/types'

/** Saves some settings; names (never values) of what changed go to analytics. */
export function useSaveTodaySettings(current: TodaySettings | undefined) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (values: Partial<TodaySettings>) => saveSettings(values),
    onSuccess: (saved, values) => {
      qc.setQueryData(todayKeys.settings, saved)
      if (current) {
        const keys = changedKeys(current, values)
        if (keys.length) trackToday('today_settings_changed', { changed_keys: keys })
      }
      void qc.invalidateQueries({ queryKey: todayKeys.plan })
    },
  })
}

/** "Update today's plan" after a settings change: opens today's plan and rebuilds the suggestions. */
export function useRebuildToday() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: () => rebuildToday('settings'),
    onSuccess: (plan) => {
      if (plan) qc.setQueryData<OpenResult>(todayKeys.plan, plan)
      toast.success(plan ? "Today's plan is updated" : 'There is no plan to update yet')
    },
  })
}
