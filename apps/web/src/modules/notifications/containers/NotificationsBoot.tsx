import { useState } from 'react'

import { useServiceWorkerRegistration } from '../hooks/useServiceWorkerRegistration'
import { listenForInstall } from '../lib/installPrompt'
import { captureLandingId } from '../lib/landing'

/**
 * Mounted once in the root layout. Registers the service worker after load, and remembers a `?n=` notification id
 * from the address the app was opened with, before the router can rewrite it. It also catches the browser's install
 * prompt, which fires before the page is interactive. Renders nothing.
 */
export function NotificationsBoot() {
  // The first render happens before the router normalises the address, which is exactly when the raw one is needed.
  useState(() => {
    if (typeof window !== 'undefined') {
      captureLandingId(window.location.search)
      // `beforeinstallprompt` fires early, so it is caught here and kept for the install offer (X-01 W4.5).
      listenForInstall()
    }
    return null
  })
  useServiceWorkerRegistration()
  return null
}
