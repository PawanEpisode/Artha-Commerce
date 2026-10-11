import type { ChapterStrength } from './schemas'

const cards = (n: number): string => `${n} ${n === 1 ? 'card' : 'cards'}`

/**
 * The one sentence of the chapter page card (FR-F15-65): "Recall strength 82%, 6 cards due". A chapter whose cards were never
 * reviewed has no strength to show, so it says so instead of "0%", and a chapter with nothing due says "nothing due".
 */
export function strengthSentence(s: Pick<ChapterStrength, 'percent' | 'due' | 'cards'>): string {
  const head = s.percent === null ? 'Not reviewed yet' : `Recall strength ${s.percent}%`
  const tail = s.due > 0 ? `${cards(s.due)} due` : s.percent === null ? `${cards(s.cards)} to learn` : 'nothing due'
  return `${head}, ${tail}`
}

/** `/app/recall/review` for one chapter: the chapter id alone is enough, the review route reads it as the source. */
export const chapterReviewSearch = (chapterId: string) => ({ chapter: chapterId }) as const

/** Whether the chapter page card shows at all: not with the flag off, not before the answer, not for a chapter with no cards. */
export const showsStrength = (enabled: boolean, data: ChapterStrength | undefined): boolean =>
  enabled && data !== undefined && data.cards > 0
