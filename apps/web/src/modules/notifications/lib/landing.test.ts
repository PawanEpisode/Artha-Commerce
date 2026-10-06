import { beforeEach, describe, expect, it } from 'vitest'

import {
  alreadyReported,
  captureLandingId,
  markReported,
  readNotificationId,
  resetLandingState,
  takeLandingId,
  withoutNotificationParam,
} from './landing'

describe('readNotificationId', () => {
  it('reads an id-shaped value', () => {
    expect(readNotificationId('?n=abc123')).toBe('abc123')
    expect(readNotificationId('?x=1&n=4f1c-9a')).toBe('4f1c-9a')
    expect(readNotificationId('n=_ok_')).toBe('_ok_')
  })

  it.each(['', '?x=1', '?n=', '?n=has space', '?n=../../etc', '?n=a%2Fb', `?n=${'a'.repeat(65)}`, '?n=<script>'])(
    'ignores %j',
    (search) => {
      expect(readNotificationId(search)).toBeNull()
    },
  )
})

describe('withoutNotificationParam', () => {
  const at = (search: string, hash = '') => ({ pathname: '/app/focus', search, hash })

  it('removes n and keeps everything else', () => {
    expect(withoutNotificationParam(at('?n=abc'))).toBe('/app/focus')
    expect(withoutNotificationParam(at('?subject=gst&n=abc&preset=deep', '#top'))).toBe(
      '/app/focus?subject=gst&preset=deep#top',
    )
  })

  it('removes every n when it repeats', () => {
    expect(withoutNotificationParam(at('?n=a&n=b'))).toBe('/app/focus')
  })

  it('is null when there is nothing to remove, so history is left alone', () => {
    expect(withoutNotificationParam(at(''))).toBeNull()
    expect(withoutNotificationParam(at('?subject=gst'))).toBeNull()
  })
})

describe('landing memory', () => {
  beforeEach(() => resetLandingState())

  it('captures the first-load id once', () => {
    captureLandingId('?n=abc')
    expect(takeLandingId()).toBe('abc')
    expect(takeLandingId()).toBeNull()
  })

  it('does not forget a captured id when a later address has none', () => {
    captureLandingId('?n=abc')
    captureLandingId('')
    expect(takeLandingId()).toBe('abc')
  })

  it('remembers what was reported', () => {
    expect(alreadyReported('abc')).toBe(false)
    markReported('abc')
    expect(alreadyReported('abc')).toBe(true)
  })
})
