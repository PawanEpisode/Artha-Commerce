import { useCallback, useLayoutEffect, useRef } from 'react'

/** A function with a fixed identity that always calls the latest closure (so handlers can sit in memoised context values). */
export function useStable<A extends unknown[], R>(fn: (...args: A) => R): (...args: A) => R {
  const ref = useRef(fn)
  useLayoutEffect(() => {
    ref.current = fn
  })
  return useCallback((...args: A) => ref.current(...args), [])
}
