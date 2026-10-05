/** Pure helpers for typing a duration as hours + minutes while the app stores whole minutes. */

export interface DurationParts {
  hours: number
  minutes: number
}

/** Whole, finite, non-negative minutes; anything else (NaN, Infinity, negatives) becomes 0. */
export function sanitizeMinutes(total: number): number {
  if (!Number.isFinite(total) || total <= 0) return 0
  return Math.round(total)
}

/** 90 -> { hours: 1, minutes: 30 }. Fractions round to the nearest minute. Values over 24 h are allowed. */
export function splitMinutes(total: number): DurationParts {
  const t = sanitizeMinutes(total)
  return { hours: Math.floor(t / 60), minutes: t % 60 }
}

/** { 1, 75 } -> 135: minutes above 59 roll over into hours. Invalid parts count as 0. */
export function joinMinutes(hours: number, minutes: number): number {
  return sanitizeMinutes(sanitizeMinutes(hours) * 60 + sanitizeMinutes(minutes))
}

/** Clamp to [0, max]. */
export function clampMinutes(total: number, maxMinutes = Number.POSITIVE_INFINITY): number {
  return Math.min(sanitizeMinutes(total), maxMinutes)
}

/**
 * short: "1 h 30 m", "45 m", "2 h". long: "1 hour 30 minutes", "45 minutes", "2 hours".
 * Zero is "0 m" / "0 minutes" so a goal of nothing is never an empty string.
 */
export function formatDuration(total: number, style: 'short' | 'long' = 'short'): string {
  const { hours, minutes } = splitMinutes(total)
  if (style === 'short') {
    if (hours === 0 && minutes === 0) return '0 m'
    return [hours > 0 ? `${hours} h` : '', minutes > 0 ? `${minutes} m` : ''].filter(Boolean).join(' ')
  }
  if (hours === 0 && minutes === 0) return '0 minutes'
  const unit = (n: number, word: string) => `${n} ${word}${n === 1 ? '' : 's'}`
  return [hours > 0 ? unit(hours, 'hour') : '', minutes > 0 ? unit(minutes, 'minute') : ''].filter(Boolean).join(' ')
}

/** Parse what a person typed in one of the two boxes: '' is null (empty), junk is null, decimals round down. */
export function parseDurationPart(raw: string): number | null {
  const trimmed = raw.trim()
  if (trimmed === '') return null
  const n = Number(trimmed)
  if (!Number.isFinite(n) || n < 0) return null
  return Math.floor(n)
}
