import { useEffect } from 'react'

import { applyAppBadge } from '../lib/appBadge'

/** Keeps the icon dot in step with `wanted`, and clears it when whatever mounted this goes away. */
export function useAppBadge(wanted: boolean) {
  useEffect(() => {
    applyAppBadge(wanted)
  }, [wanted])
  useEffect(() => () => applyAppBadge(false), [])
}
