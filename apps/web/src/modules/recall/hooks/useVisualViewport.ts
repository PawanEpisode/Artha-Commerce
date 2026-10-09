import { useEffect, useState } from 'react'

/**
 * The height of what the student can actually see, from the visual viewport. On a phone the on-screen keyboard and the
 * collapsing address bar change it, and `100vh` ignores that, which would push the rating buttons out of view. Falls back to
 * `null` (the caller uses `100dvh`) where the API is missing.
 */
export function useVisualViewportHeight(): number | null {
  const [height, setHeight] = useState<number | null>(() =>
    typeof window !== 'undefined' && window.visualViewport ? Math.round(window.visualViewport.height) : null,
  )
  useEffect(() => {
    const vv = window.visualViewport
    if (!vv) return
    const update = () => setHeight(Math.round(vv.height))
    update()
    vv.addEventListener('resize', update)
    vv.addEventListener('scroll', update)
    return () => {
      vv.removeEventListener('resize', update)
      vv.removeEventListener('scroll', update)
    }
  }, [])
  return height
}
