/**
 * The server is the clock. The page learns the offset between its own clock and the server's from each response and
 * uses it for every moment it sends (`at`, `end_at`), so a wrong device clock does not skew the stored time.
 */
let offsetMs = 0

export function setServerTime(serverIso: string, receivedAtMs = Date.now()) {
  const server = Date.parse(serverIso)
  if (Number.isFinite(server)) offsetMs = server - receivedAtMs
}

/** "Now" on the server's clock, in epoch milliseconds. */
export const nowMs = () => Date.now() + offsetMs
export const nowIso = () => new Date(nowMs()).toISOString()
export const clockOffsetMs = () => offsetMs
export const resetClock = () => {
  offsetMs = 0
}

let lastActivity = Date.now()
/** Called on pointer and key events so the server can tell a student at the keyboard from an idle one. */
export const markActive = () => {
  lastActivity = Date.now()
}
export const recentlyActive = (windowMs = 60_000) => Date.now() - lastActivity < windowMs
