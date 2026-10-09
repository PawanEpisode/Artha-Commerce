import { describe, expect, it } from 'vitest'

import { chapterTitle, forecastColumns, retentionColumns, reviewColumns, strengthOf } from './charts'
import { backlogSentence, estimate, minutesLabel, percent, plural, shortDate } from './format'
import { hubStateOf } from './hub'
import { tokenize, tokenizeLine } from './inline'
import { reviewSearchSchema, statsSearchSchema } from './search'
import { activeSection, RECALL_SECTIONS } from './sections'
import { changes, draftOf, validate } from './settingsForm'
import { SETTINGS, todayPlan } from './testing'

describe('inline card text', () => {
  it('reads bold, italic and code and leaves everything else as text', () => {
    expect(tokenizeLine('A **bold** and *slanted* and `x = 1` word')).toEqual([
      { kind: 'text', text: 'A ' },
      { kind: 'bold', text: 'bold' },
      { kind: 'text', text: ' and ' },
      { kind: 'italic', text: 'slanted' },
      { kind: 'text', text: ' and ' },
      { kind: 'code', text: 'x = 1' },
      { kind: 'text', text: ' word' },
    ])
  })
  it('never turns markup into HTML: tags stay text', () => {
    expect(tokenizeLine('<img src=x onerror=alert(1)>')).toEqual([
      { kind: 'text', text: '<img src=x onerror=alert(1)>' },
    ])
  })
  it('splits paragraphs on blank lines and keeps single line breaks', () => {
    const p = tokenize('one\ntwo\n\nthree\r\n\r\n\r\nfour')
    expect(p).toHaveLength(3)
    expect(p[0]).toHaveLength(2)
  })
  it('leaves unmatched markers alone', () => {
    expect(tokenizeLine('2 * 3 * 4')).toEqual([{ kind: 'text', text: '2 * 3 * 4' }])
    expect(tokenizeLine('**')).toEqual([{ kind: 'text', text: '**' }])
    expect(tokenizeLine('use snake_case_names here')).toEqual([{ kind: 'text', text: 'use snake_case_names here' }])
  })
})

describe('words and numbers', () => {
  it('rounds estimates kindly', () => {
    expect(estimate(0.2)).toBe('Under a minute')
    expect(estimate(12.4)).toBe('About 12 min')
    expect(estimate(60)).toBe('About 1 h')
    expect(estimate(95)).toBe('About 1 h 35 min')
  })
  it('gives a backlog as days of work, never as a bare number', () => {
    expect(backlogSentence(0, 0)).toBe('Nothing is waiting.')
    expect(backlogSentence(40, 1)).toContain('one sitting')
    expect(backlogSentence(900, 9)).toBe('900 cards are waiting. At your daily limit that clears in about 9 days.')
  })
  it('formats small things', () => {
    expect(plural(1, 'card')).toBe('1 card')
    expect(plural(2, 'day')).toBe('2 days')
    expect(percent(0.912)).toBe('91%')
    expect(percent(null)).toBe('Not enough reviews yet')
    expect(minutesLabel(0)).toBe('0 min')
    expect(minutesLabel(20)).toBe('Under a minute')
    expect(minutesLabel(3700)).toBe('1 h 2 min')
    expect(shortDate('2026-10-09')).toMatch(/Fri/)
  })
})

describe('which hub to show', () => {
  it('goes through vacation, empty, catch-up, caught up and ready in that order', () => {
    expect(hubStateOf(todayPlan({ vacation_until: '2026-10-20' }))).toBe('vacation')
    expect(hubStateOf(todayPlan({ vacation_until: '2026-10-01' }))).toBe('ready')
    expect(
      hubStateOf(
        todayPlan({
          counts: { new: 0, learning: 0, due: 0 },
          tiles: [],
          next_due_at: null,
          new_available: 0,
          queue_size: 0,
        }),
      ),
    ).toBe('empty')
    expect(hubStateOf(todayPlan({ catchup: { active: true, due: 400, oldest_overdue_days: 9 } }))).toBe('catchup')
    expect(hubStateOf(todayPlan({ queue_size: 0, counts: { new: 0, learning: 0, due: 0 } }))).toBe('caught_up')
    expect(hubStateOf(todayPlan())).toBe('ready')
  })
})

describe('chart data', () => {
  it('shapes a column per day', () => {
    const cols = reviewColumns({
      range: '7d',
      today: '2026-10-09',
      streak: 1,
      longest_streak: 1,
      reviews: 3,
      new_cards: 1,
      minutes: 2,
      ratings: { again: 0, hard: 0, good: 3, easy: 0 },
      true_retention: 1,
      series: [{ date: '2026-10-08', reviews: 3, new: 1 }],
    })
    expect(cols).toEqual([{ label: expect.stringContaining('Thu'), short: '8', values: { reviews: 3 } }])
    expect(
      retentionColumns({
        range: '7d',
        target: 0.9,
        overall: 0.88,
        series: [{ date: '2026-10-08', reviews: 5, retention: 0.876 }],
      })[0]!.values,
    ).toEqual({ retention: 88 })
    expect(
      forecastColumns({ today: '2026-10-09', overdue: 0, days: [{ date: '2026-10-09', due: 4 }] })[0]!.values,
    ).toEqual({ due: 4 })
  })
  it('names strength in words', () => {
    expect(strengthOf(0.95)).toEqual({ label: 'Strong', value: 95 })
    expect(strengthOf(0.75).label).toBe('Okay')
    expect(strengthOf(0.4).label).toBe('Needs revision')
    expect(strengthOf(null)).toEqual({ label: 'Not started', value: 0 })
    expect(chapterTitle({ chapter: null, cards: 1, due: 0, strength: null })).toBe('No chapter')
  })
})

describe('URLs', () => {
  it('falls back quietly on a hand-edited review link', () => {
    expect(reviewSearchSchema.parse({})).toMatchObject({ source: 'today' })
    expect(reviewSearchSchema.parse({ source: 'nonsense', n: '9000', chapter: 'x' })).toEqual({ source: 'today' })
    expect(reviewSearchSchema.parse({ source: 'forgotten', n: '15', tier: 'mandatory' })).toEqual({
      source: 'forgotten',
      n: 15,
      tier: 'mandatory',
    })
    expect(statsSearchSchema.parse({ range: '1y' })).toEqual({ range: '30d' })
  })
  it('lights up the section of the current page', () => {
    expect(activeSection('/app/recall', RECALL_SECTIONS)).toBe('today')
    expect(activeSection('/app/recall/stats/', RECALL_SECTIONS)).toBe('stats')
    expect(activeSection('/app/recall/review', RECALL_SECTIONS)).toBe('today')
    expect(activeSection('/app/settings/recall', RECALL_SECTIONS)).toBe('settings')
    expect(activeSection('/app/notes', RECALL_SECTIONS)).toBeUndefined()
  })
})

describe('the settings form', () => {
  it('sends only what changed, in the API names and units', () => {
    const d = { ...draftOf(SETTINGS), new_per_day: 15, retention_percent: 92, gestures: false }
    expect(changes(SETTINGS, d)).toEqual({ new_per_day: 15, desired_retention: 0.92, gestures: false })
    expect(changes(SETTINGS, draftOf(SETTINGS))).toEqual({})
  })
  it('names the allowed range for anything out of bounds', () => {
    const errors = validate({
      ...draftOf(SETTINGS),
      new_per_day: 101,
      reviews_per_day: 5,
      retention_percent: 99,
      day_start_hour: 9,
      tz: ' ',
    })
    expect(Object.keys(errors).sort()).toEqual([
      'day_start_hour',
      'new_per_day',
      'retention_percent',
      'reviews_per_day',
      'tz',
    ])
    expect(errors.new_per_day).toBe('Choose between 0 and 100.')
    expect(validate(draftOf(SETTINGS))).toEqual({})
  })
})
