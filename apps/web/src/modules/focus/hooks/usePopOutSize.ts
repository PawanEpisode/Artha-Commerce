import { useCallback } from 'react'

import { useSaveFocusSettings } from './useFocusSettings'
import { usePopOut } from './usePopOut'

/**
 * The window's size toggle: switches the layout, asks the browser for the new window size, and remembers the choice on
 * the account (`popout_size`) so the next window opens the same way.
 */
export function usePopOutSize() {
  const { size, resize } = usePopOut()
  const { mutate } = useSaveFocusSettings()
  const toggle = useCallback(() => {
    const next = size === 'pill' ? 'card' : 'pill'
    void resize(next)
    mutate({ popout_size: next })
  }, [size, resize, mutate])
  return { size, toggle }
}
