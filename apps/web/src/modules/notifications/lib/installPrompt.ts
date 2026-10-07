import { notificationAnalytics } from './analytics'
import { readEnvironment } from './browser'

/**
 * Chrome and Edge fire `beforeinstallprompt` once, early, and only let it be used from a click. So the event is caught
 * at boot (`NotificationsBoot`) and kept here until the install offer's button uses it (X-01 W4.5, FR-C7). A tiny
 * store outside React, because the event can fire before any component has mounted.
 */
export interface BeforeInstallPromptEvent extends Event {
  prompt(): Promise<void>
  userChoice: Promise<{ outcome: 'accepted' | 'dismissed' }>
}

let deferred: BeforeInstallPromptEvent | null = null
let stopListening: (() => void) | null = null
const listeners = new Set<() => void>()
const notifyAll = () => listeners.forEach((l) => l())

export const subscribeInstallPrompt = (listener: () => void) => {
  listeners.add(listener)
  return () => void listeners.delete(listener)
}
export const hasInstallPrompt = (): boolean => deferred !== null

/** Starts listening for the install events. Safe to call again; only the first call does anything. */
export function listenForInstall(target: Window = window): void {
  if (stopListening) return
  const onPrompt = (event: Event) => {
    // Keep the browser's own mini-bar away: the offer card is the one place that asks.
    event.preventDefault()
    deferred = event as BeforeInstallPromptEvent
    notifyAll()
  }
  const onInstalled = () => {
    deferred = null
    notificationAnalytics.pwaInstallResult('installed', 'prompt', readEnvironment())
    notifyAll()
  }
  target.addEventListener('beforeinstallprompt', onPrompt)
  target.addEventListener('appinstalled', onInstalled)
  stopListening = () => {
    target.removeEventListener('beforeinstallprompt', onPrompt)
    target.removeEventListener('appinstalled', onInstalled)
  }
}

/** Shows the browser's install dialog. The event works once, so it is dropped whatever the answer. */
export async function promptInstall(): Promise<'accepted' | 'dismissed' | 'unavailable'> {
  const event = deferred
  if (!event) return 'unavailable'
  deferred = null
  notifyAll()
  try {
    await event.prompt()
    return (await event.userChoice).outcome
  } catch {
    return 'dismissed'
  }
}

/** For tests: forget everything and stop listening. */
export function resetInstallPrompt(): void {
  stopListening?.()
  stopListening = null
  deferred = null
  listeners.clear()
}
