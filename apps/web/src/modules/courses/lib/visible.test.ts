import { describe, expect, it } from 'vitest'

import { studyHomeView, visibleCourses } from './visible'

const courses = [{ slug: 'ca' }, { slug: 'cs' }, { slug: 'cma' }]

describe('studyHomeView', () => {
  it('shows the catalog to a guest', () => {
    expect(studyHomeView({ ready: true, signedIn: false, courseCode: 'cma' })).toEqual({
      view: 'guest',
      courseCode: null,
    })
  })

  it('keeps the catalog until the session is known', () => {
    expect(studyHomeView({ ready: false, signedIn: false }).view).toBe('guest')
  })

  it('holds the list while a signed-in student coverage is loading', () => {
    expect(studyHomeView({ ready: false, signedIn: true, courseCode: 'cma' }).view).toBe('pending')
  })

  it('asks a signed-in student who has not chosen to pick a course', () => {
    expect(studyHomeView({ ready: true, signedIn: true, courseCode: null })).toEqual({
      view: 'choose',
      courseCode: null,
    })
  })

  it('locks the page to the chosen course', () => {
    expect(studyHomeView({ ready: true, signedIn: true, courseCode: 'CMA' })).toEqual({
      view: 'enrolled',
      courseCode: 'cma',
    })
  })
})

describe('visibleCourses', () => {
  it('returns every course when none is chosen', () => {
    expect(visibleCourses(courses, null)).toEqual(courses)
  })

  it('returns only the chosen course', () => {
    expect(visibleCourses(courses, 'cma')).toEqual([{ slug: 'cma' }])
  })

  it('keeps the catalog when the chosen course is not listed', () => {
    expect(visibleCourses(courses, 'acca')).toEqual(courses)
  })
})
