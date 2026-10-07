import { type ReactNode, useCallback, useEffect, useMemo, useSyncExternalStore } from 'react'

import { useAuth } from '~/modules/auth'
import { track, useFeatureFlag } from '~/modules/observability'

import { useDocumentPip } from '../hooks/useDocumentPip'
import { type PopOutApi, PopOutContext } from '../hooks/usePopOut'
import { notify } from '../lib/notify'
import { isDocumentPipSupported } from '../lib/pip'

const subscribeNever = () => () => undefined

/**
 * Owns the floating window for the whole app (X-01 W4.2) and reports its life to analytics. Mounted once at the root,
 * so the corner timer, the focus card and the portal all see the same window. It closes the window when the flag
 * `floating_timer` goes off or the student signs out. The timer itself is not here: `LiveMiniTimer` draws into it.
 */
export function PopOutProvider({ children }: { children: ReactNode }) {
  const { user } = useAuth()
  const flagOn = useFeatureFlag('floating_timer')
  // False while rendering on the server and while hydrating, then what the browser says, so the two renders agree.
  const supported = useSyncExternalStore(subscribeNever, isDocumentPipSupported, () => false)

  const pip = useDocumentPip({
    onClosed: ({ by, secondsOpen }) => track('popout_closed', { seconds_open: secondsOpen, by }),
  })
  const available = supported && flagOn && !!user

  const { isOpen, close: closePip, open: openPip, resize: resizePip } = pip
  useEffect(() => {
    if (isOpen && !available) closePip(flagOn ? 'student' : 'flag_off')
  }, [isOpen, available, flagOn, closePip])

  const open = useCallback<PopOutApi['open']>(
    (size, meta) => {
      if (!available) return Promise.resolve(false)
      // `openPip` asks the browser for the window before anything else, so the click is still fresh.
      return openPip(size).then((opened) => {
        if (opened) track('popout_opened', { supported: 'pip', size, source: meta.source, timer: meta.timer })
        else notify.popOutFailed()
        return opened
      })
    },
    [available, openPip],
  )

  const resize = useCallback<PopOutApi['resize']>(
    async (size) => {
      const resized = await resizePip(size)
      track('popout_size_changed', { size, resized })
      return resized
    },
    [resizePip],
  )

  const value = useMemo<PopOutApi>(
    () => ({
      available,
      isOpen,
      window: pip.window,
      root: pip.root,
      size: pip.size,
      open,
      close: () => closePip(),
      resize,
    }),
    [available, isOpen, pip.window, pip.root, pip.size, open, closePip, resize],
  )
  return <PopOutContext.Provider value={value}>{children}</PopOutContext.Provider>
}
