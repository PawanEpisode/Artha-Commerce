import { describe, expect, it } from 'vitest'

import { features } from '~/modules/catalog'

import { type FeatureViewer, groupFeatures, offerFor } from './offers'

const flagsOn: FeatureViewer['flags'] = {
  focus_timer: true,
  time_tracker: true,
  syllabus_coverage: true,
  notes: true,
  recall_system: true,
}

const guest: FeatureViewer = { signedIn: false, flags: flagsOn }
const student: FeatureViewer = { signedIn: true, flags: flagsOn }

const bySlug = (slug: string) => features.find((f) => f.slug === slug)!

describe('offerFor', () => {
  it('sends a guest to sign-in and back to the tool', () => {
    expect(offerFor(bySlug('pomodoro-focus-timer'), guest)).toMatchObject({
      destination: 'login',
      label: 'Sign in to start a focus round',
      nextPath: '/app/focus',
    })
  })

  it('opens the tool for a signed-in student', () => {
    expect(offerFor(bySlug('time-tracker'), student)).toMatchObject({
      destination: 'app',
      label: "Log today's hours",
      appPath: '/app/tracker',
    })
  })

  it('keeps a public browse link on the syllabus tracker', () => {
    expect(offerFor(bySlug('syllabus-tracker'), guest).browse).toEqual({
      to: '/courses',
      label: 'Browse the syllabus',
    })
  })

  it('labels unbuilt features as coming soon', () => {
    expect(offerFor(bySlug('mock-tests'), student)).toMatchObject({ destination: 'soon', label: 'Coming soon' })
  })

  it('hides a shipped tool when its flag is off', () => {
    const viewer: FeatureViewer = { signedIn: true, flags: { ...flagsOn, focus_timer: false } }
    expect(offerFor(bySlug('pomodoro-focus-timer'), viewer).destination).toBe('soon')
  })
})

describe('groupFeatures', () => {
  it('puts shipped tools ahead of the rest, in catalog order', () => {
    const { ready, soon } = groupFeatures(features, guest)
    expect(ready.map((o) => o.feature.slug)).toEqual([
      'pomodoro-focus-timer',
      'syllabus-tracker',
      'time-tracker',
      'streaks-analytics',
      'smart-notes',
      'revision',
    ])
    expect(soon.map((o) => o.feature.slug)).toContain('study-planner')
    expect(soon.some((o) => o.feature.status === 'live')).toBe(false)
  })
})

describe('personalised ordering and wording', () => {
  const slugs = (v: FeatureViewer) => groupFeatures(features, v).ready.map((o) => o.feature.slug)

  it('keeps catalog order for a guest and for a student with no usage data', () => {
    expect(slugs(guest)).toEqual(slugs(student))
    expect(slugs({ ...student, used: new Set() })).toEqual(slugs(student))
  })

  it('puts tools the student has not used before the ones they have', () => {
    const order = slugs({ ...student, used: new Set(['time-tracker', 'streaks-analytics', 'syllabus-tracker']) })
    expect(order[0]).toBe('pomodoro-focus-timer')
    expect(order.slice(-3)).toEqual(['syllabus-tracker', 'time-tracker', 'streaks-analytics'])
  })

  it('uses one short label for the syllabus tracker and opens notes and revision for a signed-in student', () => {
    expect(offerFor(bySlug('syllabus-tracker'), student).label).toBe('Open Tracked Syllabus')
    expect(offerFor(bySlug('smart-notes'), student)).toMatchObject({ destination: 'app', appPath: '/app/notes' })
    expect(offerFor(bySlug('revision'), student)).toMatchObject({ destination: 'app', appPath: '/app/recall' })
    expect(offerFor(bySlug('revision'), guest)).toMatchObject({ destination: 'login', nextPath: '/app/recall' })
  })
})
