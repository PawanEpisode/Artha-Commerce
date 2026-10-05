import { describe, expect, it } from 'vitest'

import { coursePrompt, coursesHomePrompt, levelPrompt, type StudyViewer, toSnapshot } from './prompt'

const snapshot = {
  courseCode: 'ca',
  courseName: 'Chartered Accountancy',
  levelCode: 'intermediate',
  levelName: 'Intermediate',
  percent: 12,
  chaptersDone: 8,
  chaptersStarted: 20,
  chaptersTotal: 70,
}

const guest: StudyViewer = { signedIn: false, coverageOn: true, snapshot: null }
const fresh: StudyViewer = { signedIn: true, coverageOn: true, snapshot: null }
const enrolled: StudyViewer = { signedIn: true, coverageOn: true, snapshot }
const off: StudyViewer = { signedIn: true, coverageOn: false, snapshot }

const ca = { slug: 'ca', name: 'CA' }
const intermediate = { slug: 'intermediate', name: 'Intermediate' }
const final = { slug: 'final', name: 'Final' }
const cs = { slug: 'cs', name: 'CS' }

describe('toSnapshot', () => {
  it('normalises codes and rounds the percent', () => {
    expect(
      toSnapshot({
        enrollment: {
          course: { code: 'CA', name: 'Chartered Accountancy' },
          level: { code: 'Intermediate', name: 'Intermediate' },
        },
        level: { pct_simple: 12.4, chapters_done: 8, chapters_total: 70 },
      }),
    ).toMatchObject({ courseCode: 'ca', levelCode: 'intermediate', percent: 12, chaptersStarted: 8 })
  })
})

describe('coursesHomePrompt', () => {
  it('invites a guest to sign in without hiding the browse', () => {
    expect(coursesHomePrompt(guest)?.link).toEqual({
      to: '/login',
      label: 'Sign in to track chapters',
      search: { next: '/app/onboarding' },
    })
  })

  it('sends a new student to set up coverage', () => {
    expect(coursesHomePrompt(fresh)?.link.to).toBe('/app/onboarding')
  })

  it('shows the real percent for an enrolled student', () => {
    const prompt = coursesHomePrompt(enrolled)
    expect(prompt?.title).toBe('Chartered Accountancy Intermediate')
    expect(prompt?.percent).toBe(12)
    expect(prompt?.body).toBe('Average progress across chapters. 8 of 70 chapters finished, 20 started.')
    expect(prompt?.progressLabel).toBe('Average progress across chapters')
    expect(prompt?.link).toEqual({ to: '/app/syllabus', label: 'Continue coverage' })
  })

  it('says nothing when coverage is switched off', () => {
    expect(coursesHomePrompt(off)).toBeNull()
  })
})

describe('coursePrompt', () => {
  it('pre-selects this course for a student who has not enrolled', () => {
    expect(coursePrompt(fresh, ca)?.link).toEqual({
      to: '/app/onboarding',
      label: 'Set up my coverage',
      search: { course: 'ca' },
    })
  })

  it('continues when this is their course', () => {
    expect(coursePrompt(enrolled, ca)?.link.label).toBe('Continue coverage')
  })

  it('keeps their own course in view when they browse another', () => {
    expect(coursePrompt(enrolled, cs)?.body).toContain('You are tracking Chartered Accountancy Intermediate')
  })
})

describe('levelPrompt', () => {
  it('asks a guest to sign in and return to this level', () => {
    expect(levelPrompt(guest, ca, intermediate)?.link).toEqual({
      to: '/login',
      label: 'Sign in to track chapters',
      search: { next: '/app/onboarding?course=ca&level=intermediate' },
    })
  })

  it('points at ticking a chapter on their own level', () => {
    expect(levelPrompt(enrolled, ca, intermediate)?.link).toEqual({ to: '/app/syllabus', label: 'Tick a chapter' })
  })

  it('names the level they are actually tracking', () => {
    expect(levelPrompt(enrolled, ca, final)?.body).toContain('You are tracking Intermediate')
    expect(levelPrompt(enrolled, ca, final)?.body).toContain('This page lists Final')
  })

  it('celebrates a finished syllabus without inventing chapters left', () => {
    const done: StudyViewer = {
      signedIn: true,
      coverageOn: true,
      snapshot: { ...snapshot, percent: 100, chaptersDone: 70 },
    }
    expect(levelPrompt(done, ca, intermediate)?.body).toBe(
      'Every chapter is finished. Open your map to revise what is due.',
    )
  })
})
