export interface TextChange {
  from: number
  to: number
  insert: string
}

const isHigh = (code: number) => code >= 0xd800 && code <= 0xdbff
const isLow = (code: number) => code >= 0xdc00 && code <= 0xdfff

/**
 * The smallest single replacement that turns `prev` into `next`, or null when they are equal. Toolbar actions return a
 * whole new text; applying only the part that changed keeps undo history, scroll position and the caret sane. Never
 * cuts an emoji (surrogate pair) in half.
 */
export function minimalChange(prev: string, next: string): TextChange | null {
  if (prev === next) return null
  const max = Math.min(prev.length, next.length)
  let from = 0
  while (from < max && prev.charCodeAt(from) === next.charCodeAt(from)) from++
  let endPrev = prev.length
  let endNext = next.length
  while (endPrev > from && endNext > from && prev.charCodeAt(endPrev - 1) === next.charCodeAt(endNext - 1)) {
    endPrev--
    endNext--
  }
  if (from > 0 && isHigh(prev.charCodeAt(from - 1)) && isLow(prev.charCodeAt(from))) from--
  if (endPrev < prev.length && isLow(prev.charCodeAt(endPrev)) && isHigh(prev.charCodeAt(endPrev - 1))) {
    endPrev++
    endNext++
  }
  return { from, to: endPrev, insert: next.slice(from, endNext) }
}
