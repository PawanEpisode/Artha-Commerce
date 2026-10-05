/**
 * "This student finished onboarding", remembered per user on this device. It exists for one case (PRD 5.1): the API
 * is down, so the gate cannot ask. A completed student is let in (fail open); an unknown or unfinished one is not
 * (fail closed). It is only ever a fallback; the server answer always wins when there is one.
 */
const key = (userId: string) => `onboarding-complete:${userId}`

export function rememberCompleted(userId: string, complete: boolean): void {
  try {
    if (complete) localStorage.setItem(key(userId), '1')
    else localStorage.removeItem(key(userId))
  } catch {
    // Storage blocked: the fallback simply is not available.
  }
}

export function wasCompleted(userId: string): boolean {
  try {
    return localStorage.getItem(key(userId)) === '1'
  } catch {
    return false
  }
}
