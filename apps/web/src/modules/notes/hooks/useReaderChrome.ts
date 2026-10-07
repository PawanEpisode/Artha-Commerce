import { useCallback, useEffect, useRef, useState } from 'react'

export const HIDE_AFTER_MS = 1000

/**
 * The distraction-free bars: they hide a second after the student starts scrolling down, come back at once on scrolling
 * up, on a tap in the middle and on any key press, and stay while something pins them (a panel, a menu).
 */
export function useReaderChrome(pinned = false) {
  const [visible, setVisible] = useState(true)
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const pinnedRef = useRef(pinned)
  pinnedRef.current = pinned

  const clear = () => {
    if (timer.current) clearTimeout(timer.current)
    timer.current = null
  }
  const show = useCallback(() => {
    clear()
    setVisible(true)
  }, [])
  const onScrollDirection = useCallback((direction: 'up' | 'down') => {
    if (direction === 'up') {
      clear()
      setVisible(true)
    } else if (!timer.current && !pinnedRef.current) {
      timer.current = setTimeout(() => {
        timer.current = null
        if (!pinnedRef.current) setVisible(false)
      }, HIDE_AFTER_MS)
    }
  }, [])
  const toggle = useCallback(() => {
    clear()
    setVisible((v) => !v)
  }, [])

  useEffect(() => {
    if (pinned) show()
  }, [pinned, show])
  useEffect(() => clear, [])

  return { visible: visible || pinned, show, toggle, onScrollDirection }
}
