import { useCallback, useEffect, useRef, useState } from 'react'

import { markActive } from '~/modules/tracker'

import { copyStyles, isDocumentPipSupported, mirrorTheme, PIP_TITLE, requestPipWindow, tryResizePip } from '../lib/pip'
import { recordPopoutTap, setPopoutOpen, setPopoutVisible } from '../lib/popout-presence'
import type { PopOutSize } from '../lib/types'
import type { PopOutCloseBy } from './usePopOut'

interface Handle {
  window: Window
  root: HTMLElement
}

interface Options {
  /** Called once when the window goes away, however it went. */
  onClosed?: (info: { by: PopOutCloseBy; secondsOpen: number }) => void
}

/**
 * Opens, follows and closes the Document Picture-in-Picture window (X-01 W4.2).
 *
 * - `open` gives the window the page's styles and theme, an element to draw into and the presence listeners (a tap in
 *   the window counts as the student being there). It must run inside a click: the browser asks for that activation.
 * - The window's own `pagehide` ends the open state, whoever closed it (the student, the browser, the tab).
 * - `resize` switches the layout, then asks the browser for the size. The window never closes and reopens, because a
 *   new window needs a click in the opener.
 */
export function useDocumentPip({ onClosed }: Options = {}) {
  const [handle, setHandle] = useState<Handle | null>(null)
  const [size, setSize] = useState<PopOutSize>('pill')
  const current = useRef<{ handle: Handle; openedAt: number; teardown: () => void } | null>(null)
  const pending = useRef(false)
  const closeBy = useRef<PopOutCloseBy>('student')
  const report = useRef(onClosed)
  useEffect(() => {
    report.current = onClosed
  })

  const finish = useCallback(() => {
    const open = current.current
    if (!open) return
    current.current = null
    open.teardown()
    setHandle(null)
    const by = closeBy.current
    closeBy.current = 'student'
    report.current?.({ by, secondsOpen: Math.round((Date.now() - open.openedAt) / 1000) })
  }, [])

  const open = useCallback(
    async (want: PopOutSize): Promise<boolean> => {
      if (current.current) return true
      if (pending.current || !isDocumentPipSupported()) return false
      pending.current = true
      try {
        // First, before any await: the browser accepts the request only while the click is still fresh.
        const win = await requestPipWindow(want)
        const doc = win.document
        doc.title = PIP_TITLE
        doc.documentElement.lang = document.documentElement.lang
        copyStyles(document, doc)
        const stopTheme = mirrorTheme(document.documentElement, doc.documentElement)
        doc.body.className = document.body.className
        doc.body.style.margin = '0'
        const root = doc.createElement('div')
        root.id = 'artha-popout-root'
        doc.body.appendChild(root)

        const onTap = () => {
          markActive()
          recordPopoutTap()
        }
        const onVisible = () => setPopoutVisible(doc.visibilityState === 'visible')
        const onOpenerGone = () => {
          closeBy.current = 'tab_closed'
        }
        win.addEventListener('pointerdown', onTap, true)
        win.addEventListener('keydown', onTap, true)
        doc.addEventListener('visibilitychange', onVisible)
        window.addEventListener('pagehide', onOpenerGone)
        win.addEventListener('pagehide', finish, { once: true })
        setPopoutOpen(true)

        const made: Handle = { window: win, root }
        current.current = {
          handle: made,
          openedAt: Date.now(),
          teardown: () => {
            stopTheme()
            win.removeEventListener('pointerdown', onTap, true)
            win.removeEventListener('keydown', onTap, true)
            doc.removeEventListener('visibilitychange', onVisible)
            window.removeEventListener('pagehide', onOpenerGone)
            setPopoutOpen(false)
          },
        }
        setSize(want)
        setHandle(made)
        return true
      } catch {
        // Refused (no activation, or the browser said no): nothing opened and nothing changed.
        return false
      } finally {
        pending.current = false
      }
    },
    [finish],
  )

  const close = useCallback(
    (by: PopOutCloseBy = 'student') => {
      const open = current.current
      if (!open) return
      closeBy.current = by
      try {
        open.handle.window.close()
      } catch {
        // already gone
      }
      finish()
    },
    [finish],
  )

  const resize = useCallback(async (next: PopOutSize): Promise<boolean> => {
    setSize(next)
    const open = current.current
    return open ? tryResizePip(open.handle.window, next) : false
  }, [])

  // The window cannot outlive the app that draws into it.
  useEffect(
    () => () => {
      const open = current.current
      if (!open) return
      current.current = null
      open.teardown()
      try {
        open.handle.window.close()
      } catch {
        // already gone
      }
    },
    [],
  )

  return {
    window: handle?.window ?? null,
    root: handle?.root ?? null,
    isOpen: handle !== null,
    size,
    setSize,
    open,
    close,
    resize,
  }
}
