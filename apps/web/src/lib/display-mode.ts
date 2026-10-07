/** `standalone` when the page runs as an installed app (display-mode standalone, or `navigator.standalone` on iOS). */
export type DisplayMode = 'browser' | 'standalone'

export function isStandalone(): boolean {
  try {
    const iosFlag = (navigator as Navigator & { standalone?: boolean }).standalone === true
    return iosFlag || window.matchMedia('(display-mode: standalone)').matches
  } catch {
    return false
  }
}

export const displayMode = (): DisplayMode => (isStandalone() ? 'standalone' : 'browser')
