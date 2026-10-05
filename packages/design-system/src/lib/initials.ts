/**
 * Initials and the stable colour of an avatar (PRD 5.5). Pure, so it is tested without a DOM.
 * Works on grapheme clusters, so Devanagari, Tamil and other scripts show a whole letter, not half of one.
 */

const segmenter =
  typeof Intl !== 'undefined' && 'Segmenter' in Intl ? new Intl.Segmenter(undefined, { granularity: 'grapheme' }) : null

function firstGrapheme(word: string): string {
  if (!segmenter) return Array.from(word)[0] ?? ''
  for (const part of segmenter.segment(word)) return part.segment
  return ''
}

const words = (text: string) => text.trim().split(/\s+/).filter(Boolean)

/** First letter of the first and of the last word of the name; one letter for one word; else the email's first letter. */
export function initialsOf(name?: string | null, email?: string | null): string {
  const parts = words(name ?? '')
  if (parts.length > 0) {
    const first = firstGrapheme(parts[0] as string)
    const last = parts.length > 1 ? firstGrapheme(parts[parts.length - 1] as string) : ''
    return `${first}${last}`.toLocaleUpperCase()
  }
  const fromEmail = firstGrapheme((email ?? '').trim())
  return fromEmail ? fromEmail.toLocaleUpperCase() : '?'
}

export const AVATAR_COLOURS = 8

/** 1 to 8, from a stable hash of the user id, so the colour never changes when the name does (FNV-1a). */
export function avatarColourIndex(seed: string): number {
  let hash = 0x811c9dc5
  for (let i = 0; i < seed.length; i++) {
    hash ^= seed.charCodeAt(i)
    hash = Math.imul(hash, 0x01000193) >>> 0
  }
  return (hash % AVATAR_COLOURS) + 1
}
