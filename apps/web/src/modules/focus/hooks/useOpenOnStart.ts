import { useCallback } from 'react'

import { shouldOpenOnStart } from '../lib/popout'
import type { FocusSettings } from '../lib/types'
import { usePopOut } from './usePopOut'

/**
 * "Pop out on start" (X-01 W4.3), kept in one place for every Start handler (the focus card, the Space shortcut and
 * Start round N in the window). Call the returned function first thing in the handler, before the start request: the
 * browser accepts the window only while the click is fresh. It does nothing unless the student turned the setting on,
 * the window is offered here and none is open.
 */
export function useOpenOnStart(settings: Pick<FocusSettings, 'popout_on_start' | 'popout_size'> | undefined) {
  const { available, isOpen, open } = usePopOut()
  const popoutOnStart = settings?.popout_on_start === true
  const size = settings?.popout_size ?? 'pill'
  return useCallback(() => {
    if (!shouldOpenOnStart({ available, popoutOnStart, popoutOpen: isOpen })) return
    void open(size, { source: 'auto_start', timer: 'idle' })
  }, [available, popoutOnStart, isOpen, open, size])
}
