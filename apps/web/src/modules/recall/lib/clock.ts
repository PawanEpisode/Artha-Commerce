/**
 * The server is the clock. The page learns the offset between its own clock and the server's from each response and uses
 * it for every moment it records (`reviewed_at`), so a wrong device clock does not skew intervals. Offline the last offset
 * is kept. Same idea as the tracker's helper, kept separate so modules do not import each other's internals.
 */
let offsetMs = 0

export function setServerTime(serverIso: string, receivedAtMs = Date.now()) {
  const server = Date.parse(serverIso)
  if (Number.isFinite(server)) offsetMs = server - receivedAtMs
}

/** "Now" on the server's clock, in epoch milliseconds. */
export const nowMs = () => Date.now() + offsetMs
export const nowDate = () => new Date(nowMs())
export const clockOffsetMs = () => offsetMs
export const resetClock = () => {
  offsetMs = 0
}
