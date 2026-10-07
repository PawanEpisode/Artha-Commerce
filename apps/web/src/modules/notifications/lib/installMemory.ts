import { readLocal, writeLocal } from './localStore'

/** What this device remembers for the install offer (a per-device convenience: losing it only repeats the offer). */
const ROUNDS_KEY = 'artha:install:rounds'
const OFFERED_KEY = 'artha:install:offered-at'

const readNumber = (key: string): number | null => {
  const value = Number(readLocal(key))
  return Number.isFinite(value) && value > 0 ? value : null
}

export const deviceRounds = (): number => readNumber(ROUNDS_KEY) ?? 0

/** Adds finished focus rounds to this device's count. */
export const addDeviceRounds = (count: number): number => {
  const next = deviceRounds() + Math.max(0, Math.floor(count))
  writeLocal(ROUNDS_KEY, String(next))
  return next
}

export const lastOfferedAt = (): number | null => readNumber(OFFERED_KEY)
export const markOffered = (now: number): void => writeLocal(OFFERED_KEY, String(now))
