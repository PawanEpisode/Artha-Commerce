import { useEffect, useState } from 'react'

/** True once `active` has held for `ms`: "this is taking longer than usual" without flashing it on fast loads. */
export function useSlow(active: boolean, ms = 3000): boolean {
  const [slow, setSlow] = useState(false)
  useEffect(() => {
    if (!active) {
      setSlow(false)
      return
    }
    const timer = window.setTimeout(() => setSlow(true), ms)
    return () => window.clearTimeout(timer)
  }, [active, ms])
  return slow
}
