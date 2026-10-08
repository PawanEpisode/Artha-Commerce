import { stepIndexFromProgress, stickyStepScrollProgress } from '@artha/design-system'
import { describe, expect, it } from 'vitest'

import { features } from '~/modules/catalog'

import { courseStories, featureBeats, featureForBeat, howItWorksBeats, walkthroughSlugs } from './story'

describe('featureBeats', () => {
  it('covers every catalog feature once, live tools first', () => {
    expect(new Set(walkthroughSlugs)).toEqual(new Set(features.map((feature) => feature.slug)))
    expect(walkthroughSlugs).toHaveLength(features.length)
    const statuses = walkthroughSlugs.map((slug) => features.find((feature) => feature.slug === slug)?.status)
    const firstSoon = statuses.indexOf('soon')
    expect(firstSoon).toBeGreaterThan(0)
    expect(statuses.slice(0, firstSoon).every((status) => status === 'live')).toBe(true)
    expect(statuses.slice(firstSoon).every((status) => status === 'soon')).toBe(true)
  })

  it('resolves each beat to a catalog feature', () => {
    for (const beat of featureBeats) {
      const feature = featureForBeat(beat)
      expect(feature.slug).toBe(beat.slug)
      expect(beat.points.length).toBeGreaterThanOrEqual(2)
      expect(beat.headline.length).toBeGreaterThan(20)
    }
  })
})

describe('course and how-it-works copy', () => {
  it('has an outcome for every course', () => {
    expect(Object.keys(courseStories).sort()).toEqual(['ca', 'cma', 'cs'])
  })

  it('has three how-it-works beats', () => {
    expect(howItWorksBeats.map((beat) => beat.id)).toEqual(['goal', 'today', 'readiness'])
  })
})

describe('walkthrough step math', () => {
  it('keeps a rail click inside the chosen beat', () => {
    const count = featureBeats.length
    for (let i = 0; i < count; i += 1) {
      expect(stepIndexFromProgress(stickyStepScrollProgress(i, count), count)).toBe(i)
    }
  })
})
