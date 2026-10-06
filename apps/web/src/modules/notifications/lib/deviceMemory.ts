/**
 * Remembers the id the API gave this browser, so the device list can say "This device" and Remove can also drop the
 * local subscription. Per-browser convenience only: the API stays the source of truth, and losing this value costs
 * nothing but the label. Every access tolerates blocked storage.
 */
const ID_KEY = 'artha:notifications:device-id'
const SYNCED_KEY = 'artha:notifications:synced-at'

const read = (key: string): string | null => {
  try {
    return window.localStorage.getItem(key)
  } catch {
    return null
  }
}
const write = (key: string, value: string | null) => {
  try {
    if (value === null) window.localStorage.removeItem(key)
    else window.localStorage.setItem(key, value)
  } catch {
    // storage blocked or full: nothing depends on it
  }
}

export const rememberDeviceId = (id: string) => write(ID_KEY, id)
export const rememberedDeviceId = () => read(ID_KEY)
export const forgetDeviceId = () => write(ID_KEY, null)

export const markSynced = (now: number) => write(SYNCED_KEY, String(now))
/** True when a registration refresh ran within `minIntervalMs`. */
export function syncedRecently(now: number, minIntervalMs: number): boolean {
  const at = Number(read(SYNCED_KEY))
  return Number.isFinite(at) && at > 0 && now - at < minIntervalMs
}
