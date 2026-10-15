import { useRouter } from '@tanstack/react-router'
import { useEffect } from 'react'

import { isNavigateMessage } from '~/sw/messages'

/**
 * Listens for navigation messages from the service worker when the student clicks a push notification
 * while a tab is already open (FR-A14). Navigates without a full page reload.
 */
export function useNotificationNavigation() {
  const router = useRouter()

  useEffect(() => {
    if (!('serviceWorker' in navigator)) return

    const onMessage = (event: MessageEvent) => {
      if (isNavigateMessage(event.data)) {
        router.history.push(event.data.path)
      }
    }
    navigator.serviceWorker.addEventListener('message', onMessage)
    return () => navigator.serviceWorker.removeEventListener('message', onMessage)
  }, [router])
}
