import { useSyncExternalStore } from 'react'

/** Whether the browser thinks it has a network, and as that changes. Always true on the server and in tests without `navigator.onLine`. */
export function useOnline(): boolean {
  return useSyncExternalStore(
    (notify) => {
      window.addEventListener('online', notify)
      window.addEventListener('offline', notify)
      return () => {
        window.removeEventListener('online', notify)
        window.removeEventListener('offline', notify)
      }
    },
    () => (typeof navigator === 'undefined' ? true : navigator.onLine !== false),
    () => true,
  )
}
