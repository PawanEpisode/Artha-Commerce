import { describe, expect, it } from 'vitest'

import { courses } from '~/modules/catalog'
import type { CourseSummary } from '~/modules/syllabus'

import { mergeCourse } from './load'

const ca = courses.find((c) => c.slug === 'ca')!

const api = (over: Partial<CourseSummary> = {}): CourseSummary => ({
  id: 'c1',
  code: 'CA',
  name: 'Chartered Accountancy',
  institute_name: 'ICAI',
  institute_url: 'https://icai.org',
  description: 'Curated description from the database.',
  levels: [
    { id: 'l2', code: 'intermediate', name: 'Intermediate', sort_order: 2 },
    { id: 'l1', code: 'foundation', name: 'Foundation', sort_order: 1 },
  ],
  ...over,
})

describe('mergeCourse', () => {
  it('returns null when neither source knows the course', () => {
    expect(mergeCourse(undefined, undefined)).toBeNull()
  })

  it('is the static entry when the API has nothing', () => {
    expect(mergeCourse(undefined, ca)).toEqual(ca)
  })

  it('takes the description from the API and keeps the catalog tagline and body names', () => {
    const merged = mergeCourse(api(), ca)!
    expect(merged.description).toBe('Curated description from the database.')
    expect(merged.tagline).toBe(ca.tagline)
    expect(merged.body).toBe(ca.body)
  })

  it('falls back to the static description when the API one is empty', () => {
    expect(mergeCourse(api({ description: '' }), ca)!.description).toBe(ca.description)
  })

  it('orders levels by the API sort order and keeps static levels the database does not have yet', () => {
    const merged = mergeCourse(api(), ca)!
    expect(merged.levels.map((l) => l.slug)).toEqual([
      'foundation',
      'intermediate',
      ...ca.levels.slice(2).map((l) => l.slug),
    ])
  })

  it('keeps the static paper names for a level until the curated syllabus supplies them', () => {
    const merged = mergeCourse(api(), ca)!
    expect(merged.levels[0]!.subjects).toEqual(ca.levels.find((l) => l.slug === 'foundation')!.subjects)
  })

  it('builds a course the catalog has never heard of from the API alone', () => {
    const merged = mergeCourse(
      api({ code: 'ACCA', name: 'ACCA', institute_name: 'ACCA Global', levels: [] }),
      undefined,
    )!
    expect(merged).toMatchObject({ slug: 'acca', name: 'ACCA', fullName: 'ACCA', body: 'ACCA Global' })
    expect(merged.levels).toEqual([])
  })
})
