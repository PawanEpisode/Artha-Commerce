import { createContext, useContext } from 'react'

import type { PopOutSize } from '../lib/types'

/**
 * Where the window was opened from: the corner timer, the focus card, the start-of-round prompt (`prompt`) or a Start
 * press with "pop out on start" on (`auto_start`).
 */
export type PopOutSource = 'mini' | 'focus_page' | 'prompt' | 'auto_start'
/** Which timer was live at that moment, for the analytics event. */
export type PopOutTimerKind = 'focus' | 'stopwatch' | 'idle'
export type PopOutCloseBy = 'student' | 'tab_closed' | 'flag_off'

/**
 * The one floating window, shared by everything that offers it: the corner timer, the focus card and the portal
 * that draws into it. `available` is false where the browser has no Document Picture-in-Picture, the `floating_timer`
 * flag is off or nobody is signed in; then nothing offers the window and an open one closes.
 */
export interface PopOutApi {
  available: boolean
  isOpen: boolean
  /** The window (null while closed): its timers and its document are the ones the timer hooks use while it is open. */
  window: Window | null
  /** The element the portal draws into. */
  root: HTMLElement | null
  /** The layout in use, which can differ from the window's real size when the browser refuses to resize. */
  size: PopOutSize
  /** Must be called from a click or key press, and it asks the browser for the window before anything is awaited. */
  open: (size: PopOutSize, meta: { source: PopOutSource; timer: PopOutTimerKind }) => Promise<boolean>
  close: () => void
  /** Switches the layout and asks the browser for the new size; true when the window really changed size. */
  resize: (size: PopOutSize) => Promise<boolean>
}

const CLOSED: PopOutApi = {
  available: false,
  isOpen: false,
  window: null,
  root: null,
  size: 'pill',
  open: async () => false,
  close: () => undefined,
  resize: async () => false,
}

export const PopOutContext = createContext<PopOutApi>(CLOSED)
export const usePopOut = () => useContext(PopOutContext)
