import { toastApiError } from '@artha/design-system'
import { useCallback, useState } from 'react'

import { annotationAnalytics } from '../lib/annotation-analytics'
import { markNotify } from '../lib/annotation-notify'
import { type ParkedMark, resolveMarkConflict } from '../lib/annotation-queue'
import type { Resolution } from '../lib/annotation-types'
import type { MarksController } from './useAnnotations'

/**
 * Comments the server could not merge (two devices changed the same words). They left the queue so nothing behind them
 * waits; the student settles them one at a time with Keep mine, Keep theirs or Keep both (FR-F03-62).
 */
export function useAnnotationConflicts(marks: Pick<MarksController, 'parked' | 'applyServerMark' | 'refreshQueue'>) {
  const [busy, setBusy] = useState(false)
  const { applyServerMark, refreshQueue } = marks

  const resolve = useCallback(
    async (conflict: ParkedMark, resolution: Resolution) => {
      setBusy(true)
      try {
        const response = await resolveMarkConflict(conflict, resolution)
        applyServerMark(response.annotation)
        annotationAnalytics.conflictResolved(resolution, response.annotation.kind)
        markNotify.conflictResolved()
        await refreshQueue()
        return true
      } catch (error) {
        toastApiError(error, 'Could not settle the conflict. Try again.')
        return false
      } finally {
        setBusy(false)
      }
    },
    [applyServerMark, refreshQueue],
  )

  return { parked: marks.parked, current: marks.parked[0] ?? null, busy, resolve }
}
