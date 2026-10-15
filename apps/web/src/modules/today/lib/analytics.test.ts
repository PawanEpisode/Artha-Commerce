import { describe, expect, it, vi } from 'vitest'

import { backlogBucket, conform, examBucket, minutesBucket, timeBucket, trackToday, WEB_EVENTS } from './analytics'
import schema from './event-schema.json'

vi.mock('~/modules/observability', () => ({ track: vi.fn() }))

describe('event schema contract (FR-F13-46)', () => {
  it('lists every event of PRD section 10 with a place', () => {
    expect(Object.keys(schema.events)).toHaveLength(26)
    for (const spec of Object.values(schema.events)) expect(['web', 'api']).toContain(spec.where)
  })
  it('never lists a property that could carry a title, a reason text or a note', () => {
    const props = new Set(Object.values(schema.events).flatMap((e) => e.props))
    for (const banned of schema.never_sent) expect(props.has(banned)).toBe(false)
  })
  it('keeps the properties of a web event and drops everything else', () => {
    const out = conform('today_task_added', {
      has_subject: true,
      est_minutes_bucket: '6-15',
      offline: false,
      title: 'Secret',
    })
    expect(out?.kept).toEqual({ has_subject: true, est_minutes_bucket: '6-15', offline: false })
    expect(out?.dropped).toEqual(['title'])
  })
  it('does not send an event the web does not own, or one that is not in the schema', () => {
    expect(conform('today_plan_generated', { trigger: 'open' })).toBeNull()
    expect(conform('not_an_event', {})).toBeNull()
    expect(trackToday('not_an_event')).toBeNull()
  })
  it('has a web event for every name the screen sends', () => {
    for (const name of [
      'today_opened',
      'today_task_started',
      'today_task_added',
      'today_task_undone',
      'today_why_opened',
      'today_celebration_viewed',
      'today_tomorrow_viewed',
      'today_overload_shown',
      'today_exam_date_prompted',
      'today_exam_date_set',
      'today_offline_queued',
      'today_offline_replayed',
      'today_settings_changed',
    ])
      expect(WEB_EVENTS).toContain(name)
  })
})

describe('buckets', () => {
  it('uses the closed lists of the schema', () => {
    expect([0, 5, 6, 15, 16, 30, 31, 60, 61].map(minutesBucket)).toEqual([
      '0-5',
      '0-5',
      '6-15',
      '6-15',
      '16-30',
      '16-30',
      '31-60',
      '31-60',
      '61+',
    ])
    expect([0, 999, 1000, 2999, 3000, 9999, 10000, 29999, 30000].map(timeBucket)).toEqual([
      'lt1s',
      'lt1s',
      '1-3s',
      '1-3s',
      '3-10s',
      '3-10s',
      '10-30s',
      '10-30s',
      '30s+',
    ])
    expect([3, 6, 21].map(backlogBucket)).toEqual(['1-5', '6-20', '21+'])
    expect([null, 10, 30, 90, 200].map(examBucket)).toEqual(['none', '<=14', '15-60', '61-120', '121+'])
  })
})
