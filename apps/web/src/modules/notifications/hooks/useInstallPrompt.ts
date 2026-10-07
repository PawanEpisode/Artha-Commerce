import { useSyncExternalStore } from 'react'

import { hasInstallPrompt, promptInstall, subscribeInstallPrompt } from '../lib/installPrompt'

/** Whether the browser handed over its install prompt (Chrome and Edge), and the call that shows it. */
export function useInstallPrompt() {
  const canPrompt = useSyncExternalStore(subscribeInstallPrompt, hasInstallPrompt, () => false)
  return { canPrompt, prompt: promptInstall }
}
