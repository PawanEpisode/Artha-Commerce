import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { trackRecall } from '../lib/analytics'
import { recallApi } from '../lib/api'
import { recallKeys } from '../lib/keys'
import type { RecallSettings } from '../lib/schemas'

export const useSettings = (enabled = true) =>
  useQuery({ queryKey: recallKeys.settings, queryFn: recallApi.settings, enabled })

export function useSaveSettings() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (patch: Partial<RecallSettings>) => recallApi.saveSettings(patch),
    onSuccess: (data, patch) => {
      qc.setQueryData(recallKeys.settings, data)
      void qc.invalidateQueries({ queryKey: recallKeys.today })
      trackRecall('recall_settings_changed', {
        changed_keys: Object.keys(patch).length,
        retention: data.desired_retention,
      })
    },
  })
}

export function useSetVacation() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (until: string | null) => recallApi.setVacation(until),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: recallKeys.settings })
      void qc.invalidateQueries({ queryKey: recallKeys.today })
    },
  })
}

export function useRebalance() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (days?: number) => recallApi.rebalance(days),
    onSuccess: (data) => {
      const moved = typeof data.moved === 'number' ? data.moved : 0
      const days = typeof data.days === 'number' ? data.days : 0
      trackRecall('recall_rebalance_used', { moved, days })
      void qc.invalidateQueries({ queryKey: recallKeys.all })
    },
  })
}
