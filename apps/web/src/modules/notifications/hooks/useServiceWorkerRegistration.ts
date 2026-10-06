import { useEffect } from 'react'

import { env, isProduction } from '~/lib/env'

import { shouldAutoRegister, SW_URL } from '../lib/serviceWorker'

/**
 * Registers `/sw.js` after the page has loaded, so it never competes with first paint. Production only, or in
 * development with `VITE_SW_DEV=true`. The worker caches nothing; registering is what makes the app installable
 * and lets a push arrive with the tab closed.
 */
export function useServiceWorkerRegistration() {
  useEffect(() => {
    const supported = 'serviceWorker' in navigator
    if (!shouldAutoRegister({ production: isProduction, swDev: env.VITE_SW_DEV === 'true', supported })) return

    const register = () => {
      navigator.serviceWorker.register(SW_URL, { scope: '/', updateViaCache: 'none' }).catch((error: unknown) => {
        console.warn('Service worker registration failed', error)
      })
    }
    if (document.readyState === 'complete') {
      register()
      return
    }
    window.addEventListener('load', register, { once: true })
    return () => window.removeEventListener('load', register)
  }, [])
}
