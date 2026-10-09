/** A random id for this install, sent with reviews so two devices can be told apart. It is not a hardware id. */
const KEY = 'artha-recall-device'
let cached: string | null = null

export function deviceId(): string | null {
  if (cached) return cached
  try {
    let id = window.localStorage.getItem(KEY)
    if (!id) {
      id = crypto.randomUUID().replaceAll('-', '').slice(0, 24)
      window.localStorage.setItem(KEY, id)
    }
    cached = id
  } catch {
    // Storage blocked: reviews are sent without a device id
  }
  return cached
}

/** Minutes east of UTC right now (India is +330). The API stores it so a review's study day can be re-derived. */
export const tzOffsetMin = (at: Date = new Date()): number => -at.getTimezoneOffset()
