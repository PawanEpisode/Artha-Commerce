/**
 * Words for "how far along": the ring is the AVERAGE of every chapter's partial percent, while "finished" counts only
 * chapters at 100%. Ticking every topic of a chapter is worth only the reading weight (40%), so a student can sit at
 * 25% overall with no chapter finished. These sentences say both numbers, so neither looks wrong.
 */
export interface ChapterCounts {
  chaptersDone: number
  chaptersStarted: number
  chaptersTotal: number
}

/** "Average progress across chapters. 0 of 119 chapters finished, 46 started." */
export function progressSentence({ chaptersDone, chaptersStarted, chaptersTotal }: ChapterCounts): string {
  if (chaptersTotal === 0) return 'Your syllabus map is ready.'
  if (chaptersDone >= chaptersTotal) return 'Every chapter is finished. Open your map to revise what is due.'
  const started = Math.max(chaptersStarted, chaptersDone)
  const startedPart = started === 0 ? 'none started yet' : `${started} started`
  return `Average progress across chapters. ${chaptersDone} of ${chaptersTotal} chapters finished, ${startedPart}.`
}

/** The same for a single paper: "35% covered. 1 of 3 chapters finished, 2 started." */
export function paperSentence(pct: number, counts: ChapterCounts): string {
  if (counts.chaptersTotal === 0) return 'Every chapter of this paper is excluded.'
  const started = Math.max(counts.chaptersStarted, counts.chaptersDone)
  const startedPart = started === 0 ? 'none started yet' : `${started} started`
  return `${pct}% covered. ${counts.chaptersDone} of ${counts.chaptersTotal} chapters finished, ${startedPart}.`
}
