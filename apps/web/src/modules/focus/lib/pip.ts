import { POPOUT_SIZES } from './popout'
import type { PopOutSize } from './types'

/**
 * Document Picture-in-Picture (X-01 PRD B): the small always-on-top window the floating timer lives in. Everything that
 * touches the browser API is here; the rest of the module only sees a `Window` and a root element. Safe to import
 * during server rendering.
 */

/** The window's accessible name. */
export const PIP_TITLE = 'Artha timer'

interface DocumentPipApi {
  requestWindow(options?: { width?: number; height?: number }): Promise<Window>
  window: Window | null
}

const pipApi = (): DocumentPipApi | null =>
  typeof window !== 'undefined' && 'documentPictureInPicture' in window
    ? (window as unknown as { documentPictureInPicture: DocumentPipApi }).documentPictureInPicture
    : null

export const isDocumentPipSupported = (): boolean => pipApi() !== null

/** Opens the window. It must be called first thing in the click (or key) handler, before anything is awaited. */
export function requestPipWindow(size: PopOutSize): Promise<Window> {
  const api = pipApi()
  if (!api) return Promise.reject(new Error('Document Picture-in-Picture is not supported'))
  const [width, height] = POPOUT_SIZES[size]
  return api.requestWindow({ width, height })
}

/**
 * Gives the window the page's styles: each sheet with an address is linked by its absolute address (a relative one
 * would not resolve in the other document); a sheet without one (dev servers inject `<style>`, libraries adopt sheets)
 * is copied as text.
 */
export function copyStyles(from: Document, to: Document): void {
  const sheets = [...Array.from(from.styleSheets), ...Array.from(from.adoptedStyleSheets ?? [])]
  for (const sheet of sheets) {
    if (sheet.href) {
      const link = to.createElement('link')
      link.rel = 'stylesheet'
      link.href = sheet.href
      to.head.appendChild(link)
      continue
    }
    try {
      const style = to.createElement('style')
      style.textContent = Array.from(sheet.cssRules, (rule) => rule.cssText).join('\n')
      to.head.appendChild(style)
    } catch {
      // A sheet the browser will not let us read is simply left out.
    }
  }
}

/**
 * Keeps the window's theme in step with the page: `data-theme`, the `class` (dark) and `color-scheme` of <html>, now
 * and whenever they change (the switcher, System at 06:00 and 18:00). Returns the function that stops following.
 */
export function mirrorTheme(fromRoot: HTMLElement, toRoot: HTMLElement): () => void {
  const apply = () => {
    const theme = fromRoot.getAttribute('data-theme')
    if (theme) toRoot.setAttribute('data-theme', theme)
    else toRoot.removeAttribute('data-theme')
    toRoot.className = fromRoot.className
    toRoot.style.colorScheme = fromRoot.style.colorScheme
  }
  apply()
  const observer = new MutationObserver(apply)
  observer.observe(fromRoot, { attributes: true, attributeFilter: ['data-theme', 'class', 'style'] })
  return () => observer.disconnect()
}

const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms))

/**
 * Asks the browser to make the window the size of `size` and reports whether it did. Chrome may refuse (a minimum
 * size, or no user activation); the caller then only switches the layout. Never closes or reopens the window.
 */
export async function tryResizePip(win: Window, size: PopOutSize): Promise<boolean> {
  const [width, height] = POPOUT_SIZES[size]
  const frame = { w: win.outerWidth - win.innerWidth, h: win.outerHeight - win.innerHeight }
  try {
    win.resizeTo(width + frame.w, height + frame.h)
  } catch {
    return false
  }
  await sleep(120)
  return Math.abs(win.innerWidth - width) <= 2 && Math.abs(win.innerHeight - height) <= 2
}
