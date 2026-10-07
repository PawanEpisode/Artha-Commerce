import { describe, expect, it } from 'vitest'

import {
  defaultTone,
  needsOcrBanner,
  openability,
  pagesBucket,
  searchMode,
  shouldSuggestNight,
  ttfpBucket,
} from './reader-state'

const base = { status: 'ready', status_reason: null, can_open: true, file_url: 'https://x/y.pdf' } as const

describe('openability', () => {
  it('opens ready, inspecting and password-protected files that have a URL', () => {
    expect(openability(base).kind).toBe('open')
    expect(openability({ ...base, status: 'inspecting' }).kind).toBe('open')
    expect(openability({ ...base, status: 'needs_password' }).kind).toBe('open')
  })

  it('waits while the server prepares the file', () => {
    expect(openability({ ...base, status: 'scanning', can_open: false, file_url: null }).kind).toBe('preparing')
    expect(openability({ ...base, status: 'reserved', can_open: false, file_url: null }).kind).toBe('preparing')
  })

  it('explains a rejected file in plain words', () => {
    const r = openability({
      ...base,
      status: 'rejected',
      status_reason: 'pdf_corrupt',
      can_open: false,
      file_url: null,
    })
    expect(r.kind).toBe('unavailable')
    expect(r.kind === 'unavailable' && r.message).toMatch(/damaged/)
    const m = openability({ ...base, status: 'rejected', status_reason: 'malware', can_open: false, file_url: null })
    expect(m.kind === 'unavailable' && m.message).toMatch(/removed/)
  })

  it('is unavailable when expired or failed, and never opens without a URL', () => {
    expect(openability({ ...base, status: 'expired', can_open: false, file_url: null }).kind).toBe('unavailable')
    expect(openability({ ...base, status: 'failed', can_open: false, file_url: null }).kind).toBe('unavailable')
    expect(openability({ ...base, file_url: null }).kind).toBe('unavailable')
  })
})

describe('reader defaults', () => {
  it('follows the Reading theme with paper, otherwise the page as printed', () => {
    expect(defaultTone('reading')).toBe('paper')
    expect(defaultTone('light')).toBe('original')
    expect(defaultTone('dark')).toBe('original')
  })

  it('suggests Night once, in Dark only', () => {
    expect(shouldSuggestNight('dark', 'original', false)).toBe(true)
    expect(shouldSuggestNight('dark', 'original', true)).toBe(false)
    expect(shouldSuggestNight('dark', 'night', false)).toBe(false)
    expect(shouldSuggestNight('light', 'original', false)).toBe(false)
  })

  it('shows the scanned banner until OCR is done', () => {
    expect(needsOcrBanner(true, 'none')).toBe(true)
    expect(needsOcrBanner(true, 'partial')).toBe(true)
    expect(needsOcrBanner(true, 'done')).toBe(false)
    expect(needsOcrBanner(false, 'none')).toBe(false)
    expect(needsOcrBanner(null, 'none')).toBe(false)
  })

  it('searches on the server for big and scanned files', () => {
    expect(searchMode(false, false)).toBe('local')
    expect(searchMode(true, false)).toBe('server')
    expect(searchMode(false, true)).toBe('server')
  })

  it('buckets without leaking numbers', () => {
    expect(ttfpBucket(400)).toBe('lt1s')
    expect(ttfpBucket(1500)).toBe('1-2s')
    expect(ttfpBucket(3000)).toBe('2-4s')
    expect(ttfpBucket(9000)).toBe('4s+')
    expect([5, 50, 300, 900].map(pagesBucket)).toEqual(['1-20', '21-100', '101-400', '400+'])
  })
})
