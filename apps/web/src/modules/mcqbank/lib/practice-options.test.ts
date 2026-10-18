import { describe, expect, it } from 'vitest'

import { defaultPracticeCount, MAX_PRACTICE_COUNT, practiceCountOptions } from './practice-options'

const values = (available: number) => practiceCountOptions(available).map((o) => o.value)

describe('practiceCountOptions', () => {
  it('offers nothing for an empty or invalid chapter', () => {
    expect(values(0)).toEqual([])
    expect(values(-3)).toEqual([])
    expect(values(Number.NaN)).toEqual([])
  })

  it('offers just the whole chapter when it is tiny', () => {
    expect(practiceCountOptions(1)).toEqual([{ value: 1, label: 'All 1' }])
    expect(values(10)).toEqual([10])
  })

  it('offers the steps that fit, then the whole chapter', () => {
    expect(values(28)).toEqual([10, 20, 28])
    expect(practiceCountOptions(28).at(-1)?.label).toBe('All 28')
    expect(values(50)).toEqual([10, 20, 50])
  })

  it('caps one session and does not call the capped value "All"', () => {
    expect(values(306)).toEqual([10, 20, 50, MAX_PRACTICE_COUNT])
    expect(practiceCountOptions(306).at(-1)?.label).toBe(`${MAX_PRACTICE_COUNT} questions`)
    expect(practiceCountOptions(MAX_PRACTICE_COUNT).at(-1)?.label).toBe(`All ${MAX_PRACTICE_COUNT}`)
  })
})

describe('defaultPracticeCount', () => {
  it('prefers 10, else everything the chapter has', () => {
    expect(defaultPracticeCount(practiceCountOptions(306))).toBe(10)
    expect(defaultPracticeCount(practiceCountOptions(7))).toBe(7)
    expect(defaultPracticeCount([])).toBeUndefined()
  })
})
