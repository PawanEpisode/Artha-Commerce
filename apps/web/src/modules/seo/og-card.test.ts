import { describe, expect, it } from 'vitest'

import { chapterCard, clamp, courseCard, marksLabel, safeText, titleSize } from './og-card'

describe('safeText', () => {
  it('maps syllabus punctuation to plain equivalents', () => {
    expect(safeText('Section A – Income Tax (₹ 50)')).toBe('Section A - Income Tax (Rs 50)')
    expect(safeText('“Quoted” and ‘single’')).toBe('"Quoted" and \'single\'')
  })

  it('drops characters the font cannot draw and collapses spaces', () => {
    expect(safeText('Tax   आयकर  Law')).toBe('Tax Law')
    expect(safeText('Emoji 🙂 here')).toBe('Emoji here')
  })

  it('keeps accented Latin letters', () => {
    expect(safeText('Café résumé')).toBe('Café résumé')
  })
})

describe('clamp', () => {
  it('leaves short text alone', () => {
    expect(clamp('Short', 20)).toBe('Short')
  })

  it('cuts long text to the limit with an ellipsis', () => {
    const out = clamp('word '.repeat(40), 30)
    expect(out.length).toBeLessThanOrEqual(30)
    expect(out.endsWith('…')).toBe(true)
  })
})

describe('titleSize', () => {
  it('shrinks as the title grows', () => {
    expect(titleSize('Short title')).toBeGreaterThan(titleSize('A '.repeat(20)))
    expect(titleSize('A '.repeat(20))).toBeGreaterThan(titleSize('A '.repeat(40)))
  })
})

describe('marksLabel', () => {
  it('formats a range, a single figure and the unknown', () => {
    expect(marksLabel('5.00', '8.00')).toBe('5 to 8')
    expect(marksLabel('6.00', '6.00')).toBe('6')
    expect(marksLabel(null, '10.00')).toBe('10')
    expect(marksLabel(null, null)).toBeNull()
  })
})

describe('cards', () => {
  it('describes a course with its levels', () => {
    const card = courseCard({
      name: 'CA',
      fullName: 'Chartered Accountancy',
      body: 'ICAI',
      levels: ['Foundation', 'Intermediate', 'Final'],
      description: 'Plan every paper.',
    })
    expect(card).toEqual({
      eyebrow: 'CA · ICAI',
      title: 'Chartered Accountancy',
      subtitle: 'Plan every paper.',
      facts: ['Foundation', 'Intermediate', 'Final'],
    })
  })

  it('describes a chapter, pluralising topics and showing marks only when known', () => {
    const base = {
      courseName: 'CA',
      levelName: 'Intermediate',
      subjectName: 'Taxation',
      chapterName: 'Income from Salaries',
    }
    expect(chapterCard({ ...base, topicCount: 1, marks: null }).facts).toEqual(['1 topic', 'Track your coverage'])
    expect(chapterCard({ ...base, topicCount: 7, marks: '5 to 8' }).facts).toEqual([
      '7 topics',
      '5 to 8 marks',
      'Track your coverage',
    ])
    expect(chapterCard({ ...base, topicCount: 7, marks: null }).eyebrow).toBe('CA · Intermediate')
  })
})

describe('og paths', () => {
  it('point at the image routes', async () => {
    const { courseOgPath, chapterOgPath } = await import('./og-card')
    expect(courseOgPath('ca')).toBe('/og/courses/ca')
    expect(chapterOgPath('ca', 'intermediate', 'taxation', 'salaries')).toBe(
      '/og/courses/ca/intermediate/taxation/salaries',
    )
  })
})
