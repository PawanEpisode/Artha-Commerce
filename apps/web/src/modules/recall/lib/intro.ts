/** Remembers, on this device only, that the first-time introduction to the review screen was seen. */
const KEY = 'artha-recall-intro-seen'

export function introSeen(): boolean {
  try {
    return window.localStorage.getItem(KEY) === '1'
  } catch {
    return false
  }
}

export function markIntroSeen(): void {
  try {
    window.localStorage.setItem(KEY, '1')
  } catch {
    // Storage blocked: the introduction shows again next time, which is harmless
  }
}
