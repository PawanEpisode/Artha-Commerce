import { describe, expect, it } from 'vitest'

import { paperSentence, progressSentence } from './progress'

describe('progressSentence', () => {
  it('explains an average above zero with no chapter finished (the "25% with 0 of 119" report)', () => {
    expect(progressSentence({ chaptersDone: 0, chaptersStarted: 46, chaptersTotal: 119 })).toBe(
      'Average progress across chapters. 0 of 119 chapters finished, 46 started.',
    )
  })

  it('says none started when nothing has begun', () => {
    expect(progressSentence({ chaptersDone: 0, chaptersStarted: 0, chaptersTotal: 12 })).toBe(
      'Average progress across chapters. 0 of 12 chapters finished, none started yet.',
    )
  })

  it('never reports fewer started than finished', () => {
    expect(progressSentence({ chaptersDone: 3, chaptersStarted: 0, chaptersTotal: 10 })).toContain('3 started')
  })

  it('celebrates a finished syllabus and handles an empty one', () => {
    expect(progressSentence({ chaptersDone: 5, chaptersStarted: 5, chaptersTotal: 5 })).toMatch(/Every chapter/)
    expect(progressSentence({ chaptersDone: 0, chaptersStarted: 0, chaptersTotal: 0 })).toBe(
      'Your syllabus map is ready.',
    )
  })
})

describe('paperSentence', () => {
  it('keeps the percent beside finished and started counts', () => {
    expect(paperSentence(35, { chaptersDone: 1, chaptersStarted: 2, chaptersTotal: 3 })).toBe(
      '35% covered. 1 of 3 chapters finished, 2 started.',
    )
  })
})
