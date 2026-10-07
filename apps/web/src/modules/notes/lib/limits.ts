import { charCount } from '~/lib/richtext'

/** The note limits of the free plan, for the editor before `GET usage/` answers. The server enforces the real ones. */
export const FALLBACK_LIMITS = { maxNotes: 2000, maxNoteChars: 100_000, maxTags: 200, maxStorageMb: 500 } as const

export type SaveBlock = { blocked: false } | { blocked: true; reason: 'too_long'; over: number }

/** Saving is blocked over the character limit, with how many characters to remove (FR "Very long note"). */
export function saveBlock(body: string, maxChars: number = FALLBACK_LIMITS.maxNoteChars): SaveBlock {
  const over = charCount(body) - maxChars
  return over > 0 ? { blocked: true, reason: 'too_long', over } : { blocked: false }
}

/** Where to cut a note in two so each half stays under the limit: at a blank line near the middle, else at the middle. */
export function splitPoint(body: string): number {
  const middle = Math.floor(body.length / 2)
  const before = body.lastIndexOf('\n\n', middle)
  const after = body.indexOf('\n\n', middle)
  const candidates = [before, after].filter((i) => i > 0)
  if (candidates.length === 0) return middle
  return candidates.reduce((best, i) => (Math.abs(i - middle) < Math.abs(best - middle) ? i : best))
}

export function splitNote(body: string): [string, string] {
  const at = splitPoint(body)
  return [body.slice(0, at).trimEnd(), body.slice(at).trimStart()]
}

/** Does `used` of `limit` reach the warning level (90 percent)? */
export const nearLimit = (used: number, limit: number) => limit > 0 && used / limit >= 0.9
