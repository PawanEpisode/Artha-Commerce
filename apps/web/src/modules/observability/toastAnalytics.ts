import { toastStore } from '@artha/design-system'
import { useEffect } from 'react'

import { track } from './analytics'
import { toastSampleRate } from './buckets'

/**
 * `toast_shown` (PRD 10): the toast's id and variant only, never its text. Toasts without an explicit id are skipped,
 * because an auto-numbered id says nothing about which message it was.
 */
export function useToastAnalytics(random: () => number = Math.random) {
  useEffect(
    () =>
      toastStore.onShow((record) => {
        if (record.id.startsWith('toast-')) return
        if (random() < toastSampleRate(record.variant))
          track('toast_shown', { key: record.id, variant: record.variant })
      }),
    [random],
  )
}
