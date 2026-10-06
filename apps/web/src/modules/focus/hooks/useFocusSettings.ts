import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { track } from '~/modules/observability'

import { getSettings, putSettings } from '../lib/api'
import { focusKeys } from '../lib/keys'
import type { FocusSettings, FocusState } from '../lib/types'

export const useFocusSettings = () =>
  useQuery({
    queryKey: focusKeys.settings,
    queryFn: getSettings,
  })

export function useSaveFocusSettings() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (patch: Partial<FocusSettings>) => putSettings(patch),
    onSuccess: ({ changed, ...settings }) => {
      qc.setQueryData(focusKeys.settings, settings)
      qc.setQueryData<FocusState>(focusKeys.timer, (old) => (old ? { ...old, settings } : old))
      if (changed.length > 0) track('focus_settings_changed', { keys: changed })
    },
  })
}
